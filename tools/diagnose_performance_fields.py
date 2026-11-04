"""Local-only private DB diagnosis. Stdout/files contain aggregate counts only.

Use --view to inspect titles/candidates in a local desktop window. Titles and
raw rows are never printed, logged, or written to the diagnostic summary.
Without --apply, the source database is opened read-only and never changed.
"""
import argparse
import copy
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_client.enrichment import SemanticClassifier, _text, _technology_text, enrich_rows
from src.local_client.technical_classifier import extract_phrases, direct_mentions
from src.local_client.upload_store import load_enrichment_preview, save_enriched_preview


def legacy_diagnosis(classifier, rows):
    """Replay v1/v2 whole-row rule, including its actual margin rejection."""
    vectors = classifier.encoder.encode([_technology_text(_text(row)) for row in rows])
    config = classifier.config
    labels = classifier.legacy_technical
    size, work_size = len(labels), len(classifier.work)
    details = []
    for row, vector in zip(rows, vectors):
        scores = classifier.prototypes[:size] @ vector
        order = sorted(range(size), key=lambda i: -float(scores[i]))
        top, runner = float(scores[order[0]]), float(scores[order[1]])
        unknown = float(max(classifier.prototypes[size+work_size:] @ vector))
        margin = top-runner
        reason = ('NO_TEXT' if sum(c.isalpha() for c in _text(row)) < 4 else
                  'LOW_SCORE' if top < config['min_cosine'] else
                  'LOW_MARGIN' if margin < config['min_margin'] else
                  'NO_LABEL_MATCH' if top <= unknown+.012 else 'NOT_ANALYZED_OR_LEGACY_DATA')
        stored = row.ai_evidence.get('technical_field', {})
        basis = 'replayed_legacy_rule'
        stored_reason = stored.get('reason')
        if stored_reason:
            reason, basis = stored_reason, 'stored_evidence'
        elif stored.get('accepted') is False and 'cosine' in stored and 'margin' in stored:
            # INT8 embeddings can vary slightly with padding/batch composition.
            # Prefer the exact scores retained during the original rejection.
            top, margin = stored['cosine'], stored['margin']
            reason = ('LOW_SCORE' if top < config['min_cosine'] else
                      'LOW_MARGIN' if margin < config['min_margin'] else 'NO_LABEL_MATCH')
            basis = 'stored_evidence'
        details.append({'project_name': row.project_name, 'legacy_reason': reason,
            'reason_basis': basis,
            'legacy_margin': round(margin, 6), 'legacy_unknown_cosine': round(unknown, 6),
            'legacy_top5': [{'name': labels[i][0], 'score': round(float(scores[i]), 6)} for i in order[:5]],
            'direct_terms': direct_mentions(row.project_name, config),
            'title_phrases': extract_phrases(row.project_name),
            'stored_evidence': stored})
    return details


def diagnose(database, *, apply=False):
    calls = []
    def guard(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'urllib.Request'):
            calls.append(event)
            raise RuntimeError('DIAGNOSTIC_NETWORK_FORBIDDEN')
    sys.addaudithook(guard)
    preview = load_enrichment_preview(database)
    original = copy.deepcopy(preview.rows)
    pending = [r for r in preview.rows if r.technical_field in ('', None, '미분류')]
    before = len(pending)
    classifier = None
    try:
        classifier = SemanticClassifier()
        details = legacy_diagnosis(classifier, pending)
    except Exception:
        details = [{'project_name': r.project_name, 'legacy_reason': 'MODEL_ERROR',
                    'legacy_top5': [], 'legacy_margin': None, 'title_phrases': extract_phrases(r.project_name)} for r in pending]
    finally:
        if classifier:
            classifier.close()
    preview.rows = pending
    warning = enrich_rows(pending)
    after = sum(r.technical_field in ('', None, '미분류') for r in pending)
    for detail, row in zip(details, pending):
        detail['new_fields'] = row.technical_fields
        detail['new_tags'] = row.technical_tags
        detail['new_evidence'] = row.ai_evidence.get('technical_field', {})
    summary = {'status': 'OK', 'total_records': len(original), 'before_unclassified': before,
               'after_unclassified': after, 'newly_classified': before-after, 'applied': False,
               'legacy_reasons': dict(Counter(d['legacy_reason'] for d in details)),
               'new_reasons': dict(Counter(r.ai_evidence.get('technical_field', {}).get('reason') or
                   ('MODEL_ERROR' if warning else 'NO_LABEL_MATCH') for r in pending if r.technical_field in ('', None, '미분류'))),
               'external_calls': len(calls), 'fallback': bool(warning)}
    protected = ('management_id', 'client', 'start_date', 'end_date', 'year', 'amount', 'raw_source')
    originals = {r.performance_id: r for r in original}
    summary['protected_field_changes'] = sum(getattr(r, f) != getattr(originals[r.performance_id], f) for r in pending for f in protected)
    summary['user_field_changes'] = sum(getattr(r, f) != getattr(originals[r.performance_id], f) for r in pending
                                      for f, source in originals[r.performance_id].field_sources.items()
                                      if source == 'user' and hasattr(r, f))
    if calls or summary['protected_field_changes'] or summary['user_field_changes']:
        raise RuntimeError('PRIVATE_DIAGNOSTIC_INVARIANT')
    if apply and pending:
        backup = Path('.run/private-diagnostics')/('before-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        result = save_enriched_preview(database, preview)
        reloaded = load_enrichment_preview(database)
        summary.update(applied=True, saved=result.updated, failed=result.failed,
            after_unclassified=sum(r.technical_field in ('', None, '미분류') for r in reloaded.rows))
        summary['newly_classified'] = before-summary['after_unclassified']
    return summary, details


def show_private(details):
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('로컬 실적 진단 — 제목은 이 창에서만 표시')
    root.geometry('1250x780')
    tk.Label(root, text='실제 제목과 후보는 로컬 화면에서만 확인합니다. 파일/로그에는 통계만 저장합니다.').pack(anchor='w', padx=12, pady=10)
    tree = ttk.Treeview(root, columns=('title', 'reason', 'new'), show='headings', height=12)
    for name, title, width in [('title','실적명',650),('reason','기존 탈락 이유',220),('new','새 broad 분야',320)]:
        tree.heading(name,text=title)
        tree.column(name,width=width)
    tree.pack(fill='x',padx=12)
    text = tk.Text(root,wrap='word')
    text.pack(fill='both',expand=True,padx=12,pady=12)
    for i, detail in enumerate(details):
        tree.insert('', 'end', iid=str(i), values=(detail.get('project_name'), detail['legacy_reason'],
            ' · '.join(v['name'] for v in detail.get('new_fields', []))))
    def select(event):
        if tree.selection():
            text.delete('1.0', 'end')
            text.insert('1.0', json.dumps(details[int(tree.selection()[0])],ensure_ascii=False,indent=2))
    tree.bind('<<TreeviewSelect>>',select)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--view', action='store_true', help='Show private titles/top5/reasons in local GUI only')
    parser.add_argument('--apply', action='store_true', help='Save to selected DB after a local SQLite backup')
    options = parser.parse_args()
    paths = [options.db] if options.db else [Path(os.environ.get('LOCALAPPDATA', '.'))/'NoticeCrawling/performance.db', Path('local/performance.db')]
    database = next((p for p in paths if p and p.is_file()), None)
    if database is None:
        print(json.dumps({'status':'REAL_DATABASE_NOT_FOUND','before_unclassified':None,'after_unclassified':None,'newly_classified':None}))
        return 2
    try:
        summary, details = diagnose(database, apply=options.apply)
    except Exception as error:
        print(json.dumps({'status':'ERROR','error_type':type(error).__name__}))
        return 1
    folder = Path('.run/private-diagnostics')
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True))
    if options.view:
        show_private(details)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
