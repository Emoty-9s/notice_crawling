"""Read-only history audit: no AI, state/cache writes or private input files."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from src.ai.prefilter import Prefilter
from src.core.storage import JsonStorage
from src.core.eligibility import current_analysis, deadline_state, eligible_active_notices


def audit(data_dir, *, now=None):
    now = now or datetime.now(timezone.utc)
    store = JsonStorage(data_dir)
    before = hashlib.sha256(store.notices_path.read_bytes()).hexdigest()
    notices = store.load_notices()
    prefilter = Prefilter()
    prepared = [prefilter.evaluate(n,now.isoformat()) for n in notices]
    active = [n for n in prepared if deadline_state(n.apply_end,today=now,title=n.title,content=n.content_text) != 'EXPIRED']
    targets = [n for n in active if n.analysis.prefilter_status in {'CANDIDATE','REVIEW'}]
    report = dict(total_history=len(notices),active=len(active),prefilter_policy=prefilter.version,
        history_prefilter_counts={s:sum(n.analysis.prefilter_status==s for n in prepared) for s in ('CANDIDATE','REVIEW','CLEARLY_UNRELATED')},
        active_prefilter_counts={s:sum(n.analysis.prefilter_status==s for n in active) for s in ('CANDIDATE','REVIEW','CLEARLY_UNRELATED')},
        current_success=sum(current_analysis(n) for n in active),legacy_success=sum(n.gemini.status=='SUCCESS' for n in notices),
        local_analysis_targets=len(targets),central_ai_calls=0,
        public_eligible=len(eligible_active_notices(prepared,today=now)),
        excluded_samples=[dict(notice_id=n.notice_id,title=n.title,reason_code=n.analysis.prefilter_reason_code,
                               body_excerpt=n.content_text[:300]) for n in prepared if n.analysis.prefilter_status=='CLEARLY_UNRELATED'][:15])
    assert hashlib.sha256(store.notices_path.read_bytes()).hexdigest() == before
    report['history_unchanged_sha256'] = before
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.data_dir),ensure_ascii=True,indent=2))
