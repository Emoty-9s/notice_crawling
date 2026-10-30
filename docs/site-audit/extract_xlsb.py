"""Read M01 source cells and hyperlink relationships using only stdlib.

This is an audit extraction helper, not a site scraper. The source is read-only.
"""

import collections
import json
import hashlib
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import xml.etree.ElementTree as ET
import zipfile


def records(data):
    offset = 0
    while offset < len(data):
        tag = data[offset] & 0x7F
        more = data[offset] & 0x80
        offset += 1
        if more:
            tag |= (data[offset] & 0x7F) << 7
            offset += 1
        size = 0
        for shift in (0, 7, 14, 21):
            byte = data[offset]
            offset += 1
            size |= (byte & 0x7F) << shift
            if not byte & 0x80:
                break
        end = offset + size
        assert end <= len(data), (tag, offset, size)
        yield tag, data[offset:end]
        offset = end


def wide(data, offset):
    size = struct.unpack_from('<I', data, offset)[0]
    end = offset + 4 + size * 2
    assert end <= len(data)
    return data[offset + 4:end].decode('utf-16le'), end


def extract(path):
    with zipfile.ZipFile(path) as archive:
        strings = [wide(payload, 1)[0] for tag, payload in
                   records(archive.read('xl/sharedStrings.bin')) if tag == 19]
        sheets = []
        for member in archive.namelist():
            if not member.startswith('xl/worksheets/sheet') or not member.endswith('.bin'):
                continue
            relpath = member.replace('/sheet', '/_rels/sheet') + '.rels'
            rels = {el.attrib['Id']: el.attrib for el in
                    ET.fromstring(archive.read(relpath))}
            cells = []
            links = []
            counts = collections.Counter()
            merges = []
            row = None
            for tag, payload in records(archive.read(member)):
                counts[tag] += 1
                if tag == 0:
                    row = struct.unpack_from('<I', payload)[0] + 1
                elif tag in (6, 7):
                    col = struct.unpack_from('<I', payload)[0] + 1
                    value = strings[struct.unpack_from('<I', payload, 8)[0]] if tag == 7 else wide(payload, 8)[0]
                    cells.append({'row': row, 'column': col, 'value': value})
                elif tag == 176:
                    r1, r2, c1, c2 = struct.unpack_from('<IIII', payload)
                    merges.append([r1 + 1, r2 + 1, c1 + 1, c2 + 1])
                # BrtHLink contains a range followed by a relationship id.
                if b'r\x00I\x00d\x00' in payload:
                    try:
                        rid, _ = wide(payload, 16)
                        if rid in rels and rels[rid]['Type'].endswith('/hyperlink'):
                            r1, r2, c1, c2 = struct.unpack_from('<IIII', payload)
                            links.append({'row': r1 + 1, 'last_row': r2 + 1,
                                          'column': c1 + 1, 'last_column': c2 + 1,
                                          'target': rels[rid]['Target'], 'relationship': rid})
                    except (AssertionError, struct.error, UnicodeDecodeError):
                        pass
            assert len(links) == sum(el['Type'].endswith('/hyperlink') for el in rels.values())
            sheets.append({'member': member, 'cells': cells, 'hyperlinks': links,
                           'merges': merges, 'record_counts': dict(counts)})
        return {'source_file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'shared_strings': len(strings), 'sheets': sheets}


def source_urls(result):
    """Keep all URL-bearing cells and links with exact row provenance."""
    output = []
    for i, sheet in enumerate(result['sheets'], 1):
        cells = {(c['row'], c['column']): c['value'] for c in sheet['cells']}

        def value_at(row, col):
            if (row, col) in cells:
                return cells[row, col]
            for r1, r2, c1, c2 in sheet['merges']:
                if r1 <= row <= r2 and c1 <= col <= c2:
                    return cells.get((r1, c1), '')
            return ''

        references = {}
        for cell in sheet['cells']:
            for url in re.findall(r'https?://[^\s<>]+', cell['value']):
                references.setdefault((cell['row'], cell['column'], url), []).append('cell_text')
        for link in sheet['hyperlinks']:
            references.setdefault((link['row'], link['column'], link['target']), []).append('hyperlink')
        for (row, col, url), kinds in sorted(references.items()):
            parts = urlsplit(url)
            # Never replay the workbook's historical PHP session identifier.
            query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                     if k.lower() != 'phpsessid']
            normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                                    parts.path or '/', urlencode(query), ''))
            display_url = url
            if any(k.lower() == 'phpsessid' for k, _ in parse_qsl(parts.query)):
                display_url = re.sub(r'(?i)(PHPSESSID=)[^&\s]+', r'\1[REDACTED]', url)
            output.append({'sheet': f'Sheet{i}', 'row': row, 'column': col,
                           'institution_cell': value_at(row, 2) if i == 1 else '',
                           'label': value_at(row, col), 'source_url': display_url,
                           'normalized_url': normalized, 'kinds': kinds})
    return {'source_file': result['source_file'], 'sha256': result['sha256'],
            'sheets': [{'name': f'Sheet{i}', 'string_cells': len(s['cells']),
                        'hyperlinks': len(s['hyperlinks']), 'merges': len(s['merges'])}
                       for i, s in enumerate(result['sheets'], 1)],
            'url_occurrences': output}


if __name__ == '__main__':
    source = next(Path('.').glob('*.xlsb'))
    result = extract(source)
    extracted = source_urls(result)
    # Save only source columns relevant to the URL inventory.
    for entry in extracted['url_occurrences']:
        entry['label'] = re.sub(r'(?i)(PHPSESSID=)[^&\s]+', r'\1[REDACTED]', entry['label'])
    target = Path('docs/site-audit/SOURCE_EXTRACT.json')
    target.write_text(json.dumps(extracted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    unique = {}
    for entry in extracted['url_occurrences']:
        unique.setdefault(entry['normalized_url'], []).append(entry)
    print('Occurrences:', len(extracted['url_occurrences']), 'Unique normalized URLs:', len(unique))
    for n, (url, refs) in enumerate(unique.items(), 1):
        print(n, refs[0]['institution_cell'] or refs[0]['label'], url,
              ','.join(f"{r['sheet']}!R{r['row']}C{r['column']}" for r in refs))
