"""Public, allowlisted central health projection. Never serialize private state."""
from datetime import datetime

SOURCES = {
    'khidi_business': '한국보건산업진흥원',
    'kised_bid_public': '창업진흥원',
    'rda_bid': '농촌진흥청',
    'seoul_rnd_notice': '서울경제진흥원',
    'kipa_bid': '한국발명진흥회',
    'kista_ippro': '한국특허전략개발원',
    'ripc_pms': '지역지식재산센터',
    'tipa_legacy_bid': '중소기업기술정보진흥원',
    'kiat_home': '한국산업기술진흥원',
}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('INVALID_SOURCE_STATUS')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('INVALID_SOURCE_STATUS')
    return parsed


def public_source_status(statuses, generated_at):
    timestamp(generated_at)
    sources = []
    for source in SOURCES:
        record = statuses.get(source, {})
        state = record.get('status')
        checked = record.get('last_attempt_at')
        count = record.get('notices_found')
        if checked is not None:
            timestamp(checked)
        sources.append(dict(source_id=source,
                            status=state if checked is not None and state in ('SUCCESS', 'ERROR') else 'UNKNOWN',
                            checked_at=checked,
                            notices_found=count if type(count) is int and count >= 0 else None))
    return {'schema_version': 1, 'generated_at': generated_at, 'sources': sources}


def validate_source_status(document):
    if (not isinstance(document, dict) or set(document) != {'schema_version', 'generated_at', 'sources'}
            or type(document['schema_version']) is not int or document['schema_version'] != 1
            or not isinstance(document['sources'], list)):
        raise ValueError('INVALID_SOURCE_STATUS')
    timestamp(document['generated_at'])
    seen = set()
    for row in document['sources']:
        if (not isinstance(row, dict) or set(row) != {'source_id', 'status', 'checked_at', 'notices_found'}
                or not isinstance(row['source_id'], str) or row['source_id'] not in SOURCES
                or row['source_id'] in seen or row['status'] not in ('SUCCESS', 'ERROR', 'UNKNOWN')
                or (row['notices_found'] is not None and
                    (type(row['notices_found']) is not int or row['notices_found'] < 0))):
            raise ValueError('INVALID_SOURCE_STATUS')
        if row['checked_at'] is not None:
            timestamp(row['checked_at'])
        elif row['status'] != 'UNKNOWN':
            raise ValueError('INVALID_SOURCE_STATUS')
        seen.add(row['source_id'])
    if seen != set(SOURCES):
        raise ValueError('INVALID_SOURCE_STATUS')
    return document
