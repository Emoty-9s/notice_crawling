"""Manual-label semantic validation; fixtures and private texts remain local."""
import json
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_client.upload import UploadRow
from src.local_client.enrichment import SemanticClassifier, _technology_text, _work_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', default='validation.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    cases = json.loads((Path(__file__).parent/'fixtures/performance_enrichment'/args.fixture).read_text(encoding='utf-8'))
    start = time.perf_counter()
    classifier = SemanticClassifier()
    texts = ['\n'.join(v for v in (c.get('title'), c.get('description')) if v) for c in cases]
    values = [UploadRow('validation', i+1, None, case.get('title'), None, None, None, None, '', '',
                        case.get('description') or '', (), None, {'columns': {}}, text, text, str(i), [],
                        field_sources={'project_name': 'excel_header'}) for i, (case, text) in enumerate(zip(cases, texts))]
    classifier.enrich(values)
    rows = []
    for index, case in enumerate(cases):
        technical = values[index].ai_evidence.get('technical_field', {'name':'미분류','ranked':[],'cosine':0,'margin':0})
        work = values[index].ai_evidence.get('work_type', {'name':'미분류','ranked':[],'cosine':0,'margin':0})
        rows.append({'index': index, 'technical_expected': case['technical'], 'technical': technical,
                     'work_expected': case['work'], 'work': work})
    known = [r for r in rows if r['technical_expected']]
    known_work = [r for r in rows if r['work_expected']]
    unknown_predictions = [r for r in rows if r['technical']['name'] == '미분류']
    result = {'cases': len(rows), 'seconds': round(time.perf_counter()-start, 3),
              'technical_top1': sum(r['technical']['name'] == r['technical_expected'] for r in known)/len(known),
              'technical_top2_rank': sum(r['technical_expected'] in [v['name'] for v in r['technical']['ranked'][:2]] for r in known)/len(known),
              'work_accuracy': sum(r['work']['name'] == r['work_expected'] for r in known_work)/len(known_work),
              'work_accuracy_including_unknown': sum(r['work']['name'] == (r['work_expected'] or '미분류') for r in rows)/len(rows),
              'unknown_precision': sum(r['technical_expected'] is None for r in unknown_predictions)/len(unknown_predictions) if unknown_predictions else None,
              'unknown_recall': sum(r['technical']['name'] == '미분류' for r in rows if r['technical_expected'] is None)/sum(r['technical_expected'] is None for r in rows),
              'rows': rows}
    classifier.close()
    out = Path('.run/local-model-'+Path(args.fixture).stem+'.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}))
    for row in rows:
        if row['technical']['name'] != (row['technical_expected'] or '미분류') or row['work']['name'] != (row['work_expected'] or '미분류'):
            print(json.dumps({'index':row['index'], 'tech':row['technical']['name'], 'score':row['technical']['cosine'],
                              'margin':row['technical']['margin'], 'expected':row['technical_expected'],
                              'work':row['work']['name'], 'work_score':row['work']['cosine'],
                              'work_margin':row['work']['margin'], 'work_expected':row['work_expected']},ensure_ascii=True))
    if args.check and not (result['technical_top1'] >= .85 and result['technical_top2_rank'] >= .90
                          and result['work_accuracy'] >= .80 and (result['unknown_precision'] or 0) >= .90
                          and result['unknown_recall'] >= .80):
        raise SystemExit('SEMANTIC_VALIDATION_GATE_FAILED')


if __name__ == '__main__':
    main()
