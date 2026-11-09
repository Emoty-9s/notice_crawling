"""Metadata-only instrumentation; never records URLs, headers or payloads."""
import platform
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import getproxies


def environment():
    context=ssl.create_default_context()
    return dict(python=sys.version.split()[0],platform=platform.system(),openssl=ssl.OPENSSL_VERSION,
                tls_minimum=context.minimum_version.name,tls_maximum=context.maximum_version.name,
                certificate_verification=context.verify_mode.name,check_hostname=context.check_hostname,
                transport='urllib.request',connection_policy='new TCP connection per request (stdlib Connection: close)',
                proxy_environment_present=bool(getproxies()))


def error_metadata(error):
    reason=error.reason if isinstance(error,URLError) else error
    message=str(reason).lower()  # Classify only. Never serialize the original message.
    if 'handshake' in message and ('timed out' in message or 'timeout' in message):
        category='TLS_HANDSHAKE_TIMEOUT'
    elif 'reset' in message or getattr(reason,'errno',None) in {54,104,10054}:
        category='CONNECTION_RESET'
    elif isinstance(reason,TimeoutError) or 'timed out' in message:
        category='TIMEOUT'
    elif isinstance(error,HTTPError):
        category='HTTP_ERROR'
    else:
        category='REQUEST_FAILED'
    return dict(exception_type=type(error).__name__,reason_type=type(reason).__name__,
                errno=getattr(reason,'errno',None) if isinstance(getattr(reason,'errno',None),int) else None,
                error_category=category)


class RequestAudit:
    """One shared pacer across anonymous sessions; no proxy/TLS/IP changes."""
    def __init__(self,events,*,interval=0,clock=time.monotonic,sleep=time.sleep):
        if not 0 <= interval <= 15: raise ValueError('interval must be between 0 and 15 seconds')
        self.events=events
        self.interval=interval
        self.clock,self.sleep=clock,sleep
        self.finished=None
        self.logical={}
        self.sessions=0

    def wrap(self,opener):
        self.sessions+=1
        return AuditedOpener(opener,self,self.sessions)


class AuditedOpener:
    def __init__(self,opener,audit,session_id):
        self.opener,self.audit,self.session_id=opener,audit,session_id

    def open(self,request,*,timeout):
        audit=self.audit
        parts=urlsplit(request.full_url)
        query=parse_qs(parts.query)
        # Stable keys exist only in memory; file IDs, issued codes and doc IDs
        # are never serialized. _/sec_code rotate during normal session refresh.
        key=(parts.path,tuple(sorted((k,tuple(v)) for k,v in query.items() if k not in {'_','sec_code'})))
        logical=audit.logical.setdefault(key,dict(identity=len(audit.logical)+1,attempts=0,failures=0))
        logical['attempts']+=1
        stage={'/portal/board/boardList':'list','/portal/board/boardView':'detail',
               '/common/File2List':'attachment_list','/common.FileDownload.do':'attachment_download'}.get(parts.path,'other')
        gap=None if audit.finished is None else max(0,audit.clock()-audit.finished)
        wait=0 if gap is None else max(0,audit.interval-gap)
        if wait: audit.sleep(wait)
        record=dict(sequence=len(audit.events)+1,logical_request=logical['identity'],stage=stage,
                    path=parts.path,session=self.session_id,attempt=logical['attempts'],retry_count=logical['failures'],
                    connection_reused=False,http_status=None,response_bytes=0,phase='connect_or_tls',
                    interval_seconds=audit.interval,wait_seconds=round(wait,3),
                    gap_before_wait=None if gap is None else round(gap,3),timeout_seconds=timeout)
        if query.get('pageNo'): record['page']=query['pageNo'][0] if query['pageNo'][0].isdecimal() else 'INVALID'
        audit.events.append(record)
        started=audit.clock()
        def finish(error=None):
            if record.get('finished'): return
            record['finished']=True
            record['elapsed_seconds']=round(audit.clock()-started,3)
            record['status']='FAILED' if error else 'SUCCESS'
            if error:
                record.update(error_metadata(error))
                if isinstance(error,HTTPError): record['http_status']=error.code
                logical['failures']+=1
            else: logical['failures']=0
            audit.finished=audit.clock()
        try:
            response=self.opener.open(request,timeout=timeout)
            record.update(http_status=response.status,phase='body',
                          open_seconds=round(audit.clock()-started,3),
                          content_type=response.headers.get_content_type())
            sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
            if isinstance(sock,ssl.SSLSocket):
                record['tls_version']=sock.version()
                cipher=sock.cipher()
                record['tls_cipher']=cipher[0] if cipher else None
            return AuditedResponse(response,record,finish)
        except Exception as error:
            finish(error)
            raise


class AuditedResponse:
    def __init__(self,response,record,finish):
        self.response,self.record,self.finish=response,record,finish
    def __getattr__(self,name): return getattr(self.response,name)
    def __enter__(self): return self
    def __exit__(self,kind,error,tb):
        try: self.response.close()
        finally: self.finish(error)
    def read(self,*args):
        data=self.response.read(*args)
        self.record['response_bytes']+=len(data)
        return data
    def read1(self,*args):
        data=self.response.read1(*args)
        self.record['response_bytes']+=len(data)
        return data
