"""Checkpointed bounded ordinary generateContent batches, not the async Batch API."""
import json
import math
import os
import random
import re
import time
from dataclasses import dataclass, replace, fields
from datetime import datetime, timedelta, timezone

from src.core.eligibility import ANALYSIS_POLICY, analysis_schema_fingerprint, current_analysis, deadline_date, deadline_state
from src.core.models import GeminiResult
from .gemini import GeminiClient, GeminiError, notice_payload, parse_batch, parse_decision, load_policy
from .prefilter import Prefilter

ANALYSIS_SCHEMA_FINGERPRINT = analysis_schema_fingerprint()


@dataclass(frozen=True)
class RunLimits:
    batch_size: int = 5
    max_api_requests_per_run: int = 12
    max_notices_per_run: int = 60
    max_input_tokens_per_run: int = 120000
    max_run_seconds: int = 600
    min_request_interval: int = 6
    max_retries: int = 2
    circuit_threshold: int = 3
    lease_seconds: int = 900
    max_batch_input_tokens: int = 18000
    max_body_chars: int = 12000

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self,field.name)
            if type(value) is not int or value < (0 if field.name in {'min_request_interval','max_retries'} else 1):
                raise ValueError('INVALID_ANALYSIS_LIMIT')
        if self.batch_size > 10 or self.max_retries > 4 or self.max_run_seconds > 1800:
            raise ValueError('INVALID_ANALYSIS_LIMIT')

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(**{f.name:int(os.environ.get('ANALYSIS_'+f.name.upper(),getattr(defaults,f.name))) for f in fields(cls)})


def utcnow():
    return datetime.now(timezone.utc)


def rate_limit_retry_at(error, now):
    if error.quota_scope in {'DAILY','ZERO'}:
        try:
            from zoneinfo import ZoneInfo
            pacific = ZoneInfo('America/Los_Angeles')
            local = now.astimezone(pacific)
            reset = datetime.combine(local.date()+timedelta(days=1),datetime.min.time(),pacific).astimezone(timezone.utc)
        except (ImportError,KeyError):
            # Windows may not have IANA tzdata. 08:00 UTC is never earlier
            # than Pacific midnight, including daylight-saving season.
            reset = now.astimezone(timezone.utc).replace(hour=8,minute=0,second=0,microsecond=0)
            if reset <= now: reset += timedelta(days=1)
    else:
        reset = now+timedelta(seconds=60 if error.quota_scope=='MINUTE' else 3600)
    return max(reset,now+timedelta(seconds=error.retry_after or 0))


def prepare(notice, prefilter, now):
    notice = prefilter.evaluate(notice,now.isoformat())
    state = notice.analysis
    if current_analysis(notice):
        if state.analysis_status != 'SUCCESS' or state.content_hash != notice.content_hash or state.analysis_policy != ANALYSIS_POLICY:
            state = replace(state,content_hash=notice.content_hash,analysis_policy=ANALYSIS_POLICY,
                            analysis_status='SUCCESS',lease_until=None,next_retry_at=None,last_error_code=None)
    elif (state.content_hash != notice.content_hash or state.analysis_policy != ANALYSIS_POLICY
          or state.target_schema_fingerprint != ANALYSIS_SCHEMA_FINGERPRINT):
        state = replace(state,content_hash=notice.content_hash,analysis_policy=ANALYSIS_POLICY,
                        target_schema_fingerprint=ANALYSIS_SCHEMA_FINGERPRINT,
                        analysis_status='STALE_POLICY' if notice.gemini.status == 'SUCCESS' else 'PENDING',
                        attempts=0,last_attempt_at=None,next_retry_at=None,lease_until=None,last_error_code=None,fallback_size=10)
    elif state.analysis_status == 'IN_PROGRESS' and (state.lease_until is None or datetime.fromisoformat(state.lease_until) <= now):
        state = replace(state,analysis_status='RETRY_WAIT',next_retry_at=now.isoformat(),lease_until=None,
                        last_error_code='LEASE_EXPIRED')
    return replace(notice,analysis=state)


def due(notice, now):
    state = notice.analysis
    return (not current_analysis(notice) and state.prefilter_status != 'CLEARLY_UNRELATED'
        and state.analysis_status not in {'IN_PROGRESS','PERMANENT_FAILURE'}
        and (state.next_retry_at is None or datetime.fromisoformat(state.next_retry_at) <= now)
        and deadline_state(notice.apply_end,today=now,title=notice.title,content=notice.content_text) != 'EXPIRED')


def queue_statistics(notices, now=None):
    from src.core.eligibility import eligible_active_notices
    now = now or utcnow()
    active = [n for n in notices if deadline_state(n.apply_end,today=now,title=n.title,content=n.content_text) != 'EXPIRED']
    targets = [n for n in active if n.analysis.prefilter_status != 'CLEARLY_UNRELATED' or current_analysis(n)]
    retry_times = [n.analysis.next_retry_at for n in targets if n.analysis.next_retry_at]
    pending = [n for n in targets if not current_analysis(n)]
    return dict(total_history=len(notices),active_notices=len(active),
        prefilter_counts={s:sum(n.analysis.prefilter_status==s for n in active) for s in ('CANDIDATE','REVIEW','CLEARLY_UNRELATED')},
        analysis_counts={s:sum(n.analysis.analysis_status==s for n in targets) for s in
            ('PENDING','IN_PROGRESS','RETRY_WAIT','SUCCESS','PERMANENT_FAILURE','STALE_POLICY')},
        current_analysis_success=sum(current_analysis(n) for n in targets),
        public_eligible=len(eligible_active_notices(notices,today=now)),
        analysis_status='PARTIAL' if pending else 'SUCCESS',
        zero_public_reason=('ANALYSIS_INCOMPLETE' if pending else 'NO_ELIGIBLE_ACTIVE_SUCCESS')
                          if not eligible_active_notices(notices,today=now) else None,
        next_retry_at=min(retry_times,key=datetime.fromisoformat) if retry_times else None)


def priority(notice, now):
    # A REVIEW waiting >= 7 days gets every fourth slot in order_queue.
    candidate = notice.analysis.prefilter_status == 'CANDIDATE'
    end = deadline_date(notice.apply_end)
    if candidate and notice.status == 'NEW':
        rank = 0 if end and (end-now.date()).days <= 7 else 1
    elif candidate and notice.status == 'UPDATED': rank = 2
    elif candidate: rank = 3
    else: rank = 4
    lifecycle = {'NEW':0,'UPDATED':1}.get(notice.status,2) if not candidate else 0
    return rank, lifecycle, end or datetime.max.date(), notice.first_seen_at, notice.notice_id


def order_queue(notices, now):
    old_review, rest = [], []
    for n in sorted(notices,key=lambda n:priority(n,now)):
        age = (now-datetime.fromisoformat(n.first_seen_at)).total_seconds()
        (old_review if n.analysis.prefilter_status == 'REVIEW' and age >= 7*86400 else rest).append(n)
    ordered = []
    while rest or old_review:
        # Even a one-notice budget gives an aged REVIEW a turn on alternating
        # calendar days; larger budgets reserve every fourth slot.
        use_review = old_review and (not rest or len(ordered)%4 == (0 if now.toordinal()%2 == 0 else 3))
        ordered.append((old_review if use_review else rest).pop(0))
    return ordered


def bounded_payload(notice, limit):
    payload = notice_payload(notice)
    def public_text(value):
        if not isinstance(value,str): return value
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[이메일 제외]', value)
        value = re.sub(r'(?<!\d)(?:\+82[- ]?)?(?:01[016789]|02|0[3-6]\d)[- ]?\d{3,4}[- ]?\d{4}(?!\d)', '[연락처 제외]', value)
        return re.sub(r'(담당자|문의자|작성자)\s*[:：]\s*[가-힣]{2,4}',r'\1: [이름 제외]',value)
    payload = {k:public_text(v) for k,v in payload.items()}
    body = payload['content_text']
    if len(body) > limit:
        # Keep beginning/end plus qualifications/work scope occurring in the
        # middle. These are verbatim excerpts, never invented requirements.
        lines = body.splitlines()
        evidence = '\n'.join(line for line in lines if any(k in line for k in
            ('자격','수행','용역','모집','특허','사업화','기술이전','신청대상')))
        quarter = limit//4
        body = body[:quarter]+'\n[중략]\n'+evidence[:limit//2]+'\n[중략]\n'+body[-quarter:]
    payload['content_text'] = body
    return {'notice_id':notice.notice_id,**payload}


def estimate_tokens(records):
    # Conservative UTF-8-byte upper bound including policy/schema overhead.
    # Exact provider usage is recorded separately when supplied by the API.
    policy_overhead = len(json.dumps(load_policy(),ensure_ascii=False).encode('utf-8'))+2048
    return len(json.dumps(records,ensure_ascii=False).encode('utf-8'))+policy_overhead


class BatchSession:
    def __init__(self, client, *, limits=None, clock=utcnow, sleep=time.sleep, monotonic=time.monotonic,
                 jitter=random.random, prefilter=None):
        self.client,self.limits,self.clock = client,limits or RunLimits.from_env(),clock
        self.sleep,self.monotonic,self.jitter = sleep,monotonic,jitter
        self.prefilter = prefilter or Prefilter()
        self.real = isinstance(client,GeminiClient)
        self.batch_capable = callable(getattr(type(client),'generate_batch',None))
        self.start = monotonic()
        self.last_start = None
        self.errors = {}
        self.stop_reason = None
        self.metrics = dict(api_requests=0,analyzed_notices=0,successful_notices=0,failed_notices=0,
            input_tokens=0,output_tokens=0,estimated_input_tokens=0,retries=0,http_429=0,http_503=0,
            timeouts=0,cache_hits=0,quota_scope=None,quota_limit=None)
        self.metrics['quota_metrics'] = []
        self.metrics['model_id'] = client.model if self.real and re.fullmatch(r'gemini-[A-Za-z0-9_.-]{1,100}',client.model) else None

    def run(self, records, enabled, checkpoint):
        if len({n.notice_id for n in records}) != len(records):
            raise ValueError('DUPLICATE_NOTICE_ID')
        now = self.clock()
        cooldowns = [datetime.fromisoformat(n.analysis.next_retry_at) for n in records
            if n.analysis.next_retry_at and (n.analysis.last_error_code or '').startswith('HTTP_429')]
        global_cooldown = max(cooldowns,default=now)
        merged = {n.notice_id:prepare(n,self.prefilter,now) for n in records}
        self.metrics['cache_hits'] = sum(current_analysis(n) for n in merged.values())
        def commit(n):
            merged[n.notice_id] = n
            checkpoint(list(merged.values()))  # Exceptions propagate; no provider call after failed claim/save.
        queue = order_queue([n for n in merged.values() if n.source_id in enabled and due(n,now)],now)
        checkpoint(list(merged.values()))
        consecutive = 0
        attempted_ids = set()
        for index,n in enumerate(queue):
            if n.gemini.status == 'NOT_ANALYZED':
                merged[n.notice_id] = replace(n,gemini=replace(n.gemini,status='PENDING'))
        while queue:
            if self.stop_reason:
                break
            now = self.clock()
            if global_cooldown > now:
                self.stop_reason = 'RATE_LIMIT_COOLDOWN'
                break
            count = min(self.limits.batch_size,queue[0].analysis.fallback_size) if self.batch_capable else 1
            capacity = self.limits.max_notices_per_run-len(attempted_ids)
            group = []
            for n in queue[:count]:
                if n.notice_id not in attempted_ids:
                    if capacity <= 0: break
                    capacity -= 1
                group.append(n)
            if not group:
                self.stop_reason = 'NOTICE_BUDGET';break
            while len(group) > 1 and estimate_tokens([bounded_payload(n,self.limits.max_body_chars) for n in group]) > self.limits.max_batch_input_tokens:
                group = group[:max(1,len(group)//2)]
            del queue[:len(group)]
            for attempt in range(self.limits.max_retries+1):
                body_limit = self.limits.max_body_chars
                records_payload = [bounded_payload(n,body_limit) for n in group]
                while estimate_tokens(records_payload) > self.limits.max_batch_input_tokens and body_limit > 256:
                    body_limit = max(256,body_limit//2)
                    records_payload = [bounded_payload(n,body_limit) for n in group]
                estimated = estimate_tokens(records_payload)
                delay = max(0,max(6,self.limits.min_request_interval)-(self.monotonic()-(self.last_start or 0))) if self.real and self.last_start is not None else 0
                elapsed = self.monotonic()-self.start
                request_timeout = self.client.timeout if self.real else 0
                if self.metrics['api_requests'] >= self.limits.max_api_requests_per_run:
                    self.stop_reason = 'REQUEST_BUDGET';queue = group+queue;break
                if self.metrics['estimated_input_tokens']+estimated > self.limits.max_input_tokens_per_run:
                    self.stop_reason = 'TOKEN_BUDGET';queue = group+queue;break
                if estimated > self.limits.max_batch_input_tokens:
                    self.stop_reason = 'INPUT_TOO_LARGE';queue = group+queue;break
                if elapsed+delay+request_timeout >= self.limits.max_run_seconds:
                    self.stop_reason = 'TIME_BUDGET';queue = group+queue;break
                if delay: self.sleep(delay)
                now = self.clock()
                for n in group:
                    state = merged[n.notice_id].analysis
                    commit(replace(merged[n.notice_id],analysis=replace(state,analysis_status='IN_PROGRESS',
                        attempts=state.attempts+1,last_attempt_at=now.isoformat(),
                        lease_until=(now+timedelta(seconds=self.limits.lease_seconds)).isoformat(),next_retry_at=None)))
                self.last_start = self.monotonic()
                self.metrics['api_requests'] += 1
                self.metrics['estimated_input_tokens'] += estimated
                self.metrics['analyzed_notices'] += len(group)
                attempted_ids.update(n.notice_id for n in group)
                if attempt: self.metrics['retries'] += 1
                error = None
                try:
                    single_fallback = (self.batch_capable and len(group)==1 and group[0].analysis.fallback_size==1
                                       and callable(getattr(type(self.client),'generate',None)))
                    if self.batch_capable and not single_fallback:
                        text = self.client.generate_batch(records_payload)
                        decisions = parse_batch(text,[n.notice_id for n in group],self.client.policy['output_schema'])
                    else:
                        text = self.client.generate({k:v for k,v in records_payload[0].items() if k!='notice_id'})
                        decisions = {group[0].notice_id:parse_decision(text,self.client.policy['output_schema'] if self.batch_capable else None)}
                except GeminiError as caught: error = caught; decisions = {}
                except (TimeoutError,ConnectionError,OSError):
                    error = GeminiError('NETWORK_OR_TIMEOUT',retryable=True); decisions = {}
                except Exception:
                    error = GeminiError('ANALYSIS_ERROR'); decisions = {}
                usage = getattr(self.client,'last_usage',{}) if self.batch_capable else {}
                if isinstance(usage,dict):
                    self.metrics['input_tokens'] += usage.get('promptTokenCount',0)
                    self.metrics['output_tokens'] += usage.get('candidatesTokenCount',0)
                if error:
                    consecutive += 1
                    status = error.http_status
                    self.metrics['http_429'] += int(status == 429)
                    self.metrics['http_503'] += int(status == 503)
                    self.metrics['timeouts'] += int(error.code == 'NETWORK_OR_TIMEOUT')
                    if status == 429:
                        self.metrics.update(quota_scope=error.quota_scope,quota_limit=error.quota_limit)
                        self.metrics['quota_metrics'] = list(error.quota_metrics)
                        global_cooldown = rate_limit_retry_at(error,self.clock())
                        self.stop_reason = 'HTTP_429_'+error.quota_scope
                    elif status in (400,401,402,403,404) or error.code in {'INVALID_INPUT_FIELDS','MISSING_OR_INVALID_CONFIGURATION','INVALID_POLICY'}:
                        self.stop_reason = 'OPERATOR_ACTION'
                    elif consecutive >= self.limits.circuit_threshold:
                        self.stop_reason = 'CIRCUIT_OPEN'
                else:
                    consecutive = 0
                now = self.clock()
                retry_group = []
                for n in group:
                    current = merged[n.notice_id]
                    if n.notice_id in decisions:
                        result = GeminiResult(status='SUCCESS',analysis_policy=ANALYSIS_POLICY,
                            analyzed_content_hash=n.content_hash,analyzed_at=now.isoformat(),**decisions[n.notice_id])
                        prior = current.analysis.previous_results
                        if current.gemini.status == 'SUCCESS' and current.gemini != result:
                            prior = (*prior,current.gemini)
                        commit(replace(current,gemini=result,analysis=replace(current.analysis,
                            analysis_status='SUCCESS',result_schema_fingerprint=ANALYSIS_SCHEMA_FINGERPRINT,
                            lease_until=None,next_retry_at=None,last_error_code=None,previous_results=prior)))
                        self.metrics['successful_notices'] += 1
                        self.errors.pop(n.notice_id,None)
                    else:
                        code = (self.stop_reason if self.stop_reason and self.stop_reason.startswith('HTTP_429')
                                else f'HTTP_{error.http_status}' if error and error.http_status
                                else error.code if error else 'MISSING_OR_INVALID_RESULT')
                        permanent = error is not None and error.http_status in (400,401,402,403,404)
                        retry_at = max(global_cooldown,now+timedelta(seconds=max(300,error.retry_after or 0) if error else 300))
                        state = replace(current.analysis,analysis_status='PERMANENT_FAILURE' if permanent else 'RETRY_WAIT',
                            lease_until=None,next_retry_at=None if permanent else retry_at.isoformat(),last_error_code=code,
                            fallback_size=(2 if len(group)>2 else 1) if not error or error.code in {'MALFORMED_JSON','INVALID_OUTPUT_SCHEMA','MALFORMED_API_RESPONSE'} else current.analysis.fallback_size)
                        commit(replace(current,analysis=state))
                        self.errors[n.notice_id] = code
                        retry_group.append(n)
                # Retry transport failures only, and split invalid batches at most
                # twice in this run. Good rows are never resubmitted.
                if not retry_group or self.stop_reason: break
                transient = error is not None and error.retryable
                malformed = not error or error.code in {'MALFORMED_JSON','INVALID_OUTPUT_SCHEMA','MALFORMED_API_RESPONSE'}
                if malformed:
                    if len(group) > 1:
                        # Smaller batches on this run; finite fallback cap carries
                        # across runs to eventually permit single-notice requests.
                        queue = [merged[n.notice_id] for n in retry_group] + queue
                    break
                if not transient or attempt >= self.limits.max_retries: break
                wait = max(error.retry_after or 0,min(30,2**(attempt+1))*(1+self.jitter()))
                if wait > 30:
                    break  # Persist provider delay; avoid spending the run asleep.
                if self.monotonic()-self.start+wait >= self.limits.max_run_seconds:
                    self.stop_reason = 'TIME_BUDGET';break
                if self.real: self.sleep(wait)
        for n in queue:
            current = merged[n.notice_id]
            if current_analysis(current): continue
            if global_cooldown > self.clock():
                current = replace(current,analysis=replace(current.analysis,analysis_status='RETRY_WAIT',
                    next_retry_at=global_cooldown.isoformat(),last_error_code=self.stop_reason if (self.stop_reason or '').startswith('HTTP_429') else 'HTTP_429_COOLDOWN'))
            self.errors[n.notice_id] = self.stop_reason or 'BUDGET_DEFERRED'
            commit(current)
        self.metrics['failed_notices'] = len(self.errors)
        self.metrics['unique_analyzed_notices'] = len(attempted_ids)
        incomplete = any(not current_analysis(n) and n.analysis.prefilter_status!='CLEARLY_UNRELATED'
            and deadline_state(n.apply_end,today=self.clock(),title=n.title,content=n.content_text)!='EXPIRED'
            for n in merged.values())
        self.metrics['stop_reason'] = self.stop_reason or ('WAITING_RETRY_OR_OPERATOR' if incomplete else 'DRAINED')
        self.metrics['elapsed_seconds'] = round(self.monotonic()-self.start,3)
        checkpoint(list(merged.values()))
        return list(merged.values())
