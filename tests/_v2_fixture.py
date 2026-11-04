"""Frozen v2 consumer fixture, preserving historical matcher input/score tests.

Not a producer: the real central renderer publishes v3. These explicit fixtures
ensure cached v2 installations remain readable without changing old scores.
"""
from src.core.normalizer import clean_content_text

def build_feed(notices,*,generated_at):
    rows=[]
    for n in sorted(notices,key=lambda n:(n.source_id,n.notice_id)):
        g=n.gemini
        text=clean_content_text(n.content_text)
        rows.append(dict(notice_id=n.notice_id,source_id=n.source_id,institution=n.institution,title=n.title,
            category=g.category,participation_type=g.participation_type,published_at=n.published_at,
            apply_start=n.apply_start,apply_end=n.apply_end,url=n.url,summary=text[:300],keywords=list(g.keywords),
            relevance_reason=g.reason,first_seen_at=n.first_seen_at,updated_at=n.updated_at,
            is_new=n.status=='NEW' and n.first_seen_at==generated_at))
    return dict(schema_version=2,generated_at=generated_at,notices=rows)
