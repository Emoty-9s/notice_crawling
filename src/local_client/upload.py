"""Deterministic local workbook ingestion. No HTTP, AI, logging or DB writes."""
from __future__ import annotations

import csv
import io
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


ALIASES = {
    'management_id': ('관리번호', '실적관리번호', '프로젝트번호', '프로젝트ID', '과제번호', '사업관리번호',
                      '내부관리번호', '실적번호', '계약번호', 'management_id', 'project_id'),
    'project_name': ('사업명', '프로젝트명', '과업명', '과제명', '용역명', '계약명', '사업과제명', '업무명', 'project_name'),
    'client': ('고객사', '고객', '발주처', '발주기관', '기관명', '수요기관', '발주사', '수행기관', '의뢰기관', 'client'),
    'description': ('수행내용', '주요업무', '업무내용', '사업내용', '과업내용', '프로젝트내용', '주요내용', '비고', '설명', 'description'),
    'year': ('수행년도', '수행연도', '연도', '사업년도', '사업연도', '계약년도', '계약연도', 'year'),
    'start_date': ('시작일', '착수일', '계약일', '수행시작일', '사업시작일', 'start_date'),
    'end_date': ('종료일', '완료일', '준공일', '수행종료일', '사업종료일', 'end_date'),
    'technical_field': ('기술분야', '분야', '산업분야', '전문분야', '사업분야', '기술영역', 'technical_field'),
    'work_type': ('업무유형', '실적유형', '사업유형', '과업유형', '용역유형', '프로젝트유형', 'work_type'),
    'amount': ('금액', '계약금액', '사업비', '용역금액', '수행금액', '총사업비', 'amount'),
    'period': ('수행기간', '사업기간', '계약기간', '기간'),
    'keywords': ('키워드', '핵심어', 'keywords'),
}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 150 * 1024 * 1024
MAX_ROWS = 50000
MAX_COLUMNS = 256
MAX_CELLS = 500000


class UploadError(ValueError):
    """Safe code only; never include cell contents or reader exceptions."""


def normalize_header(value):
    text = unicodedata.normalize('NFKC', str(value or '')).strip().casefold()
    text = re.sub(r'\([^()]*\)\s*$', '', text)
    return re.sub(r'[\s_]+', '', text)


def canonical(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())


def header_field(value):
    key = normalize_header(value)
    return next((name for name, aliases in ALIASES.items()
                 if key in {normalize_header(a) for a in aliases}), None)


def scalar(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@dataclass(frozen=True)
class Cell:
    value: object = None
    text: str = ''
    number_format: str = ''
    formula: str | None = None
    error: bool = False


def make_cell(value, number_format='', *, formula=None, error=False):
    if value is None:
        text = ''
    elif isinstance(value, (date, datetime)):
        text = value.isoformat()
    elif type(value) in (int, float) and math.isfinite(value):
        mask = number_format.split(';')[0]
        if re.fullmatch('0{2,}', mask) and float(value).is_integer() and value >= 0:
            text = str(int(value)).zfill(len(mask))
        else:
            text = str(int(value)) if float(value).is_integer() else str(value)
    else:
        text = str(value)
    return Cell(scalar(value), text, number_format, formula, error)


@dataclass
class Sheet:
    name: str
    rows: list[list[Cell]]


def _bounded(rows):
    result, cells = [], 0
    for row in rows:
        row = list(row)
        while row and not row[-1].text and not row[-1].formula:
            row.pop()
        cells += len(row)
        if len(result) >= MAX_ROWS or len(row) > MAX_COLUMNS or cells > MAX_CELLS:
            raise UploadError('WORKBOOK_LIMIT_EXCEEDED')
        result.append(row)
    return result


def _read_xlsx(path):
    import openpyxl
    with ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNPACKED_BYTES:
            raise UploadError('WORKBOOK_LIMIT_EXCEEDED')
    book = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
    cached = None
    try:
        cached = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_links=False)
        sheets = []
        for sheet in book.worksheets:
            values = cached[sheet.title]
            # Ignore inflated dimensions from old exporters; enforce our own limits.
            sheet.reset_dimensions()
            values.reset_dimensions()
            def rows():
                for original, calculated in zip(sheet.iter_rows(), values.iter_rows()):
                    row = []
                    for cell, calculated_cell in zip(original, calculated):
                        formula = cell.value if cell.data_type == 'f' else None
                        value = calculated_cell.value if formula else cell.value
                        row.append(make_cell(value, cell.number_format, formula=formula,
                                             error=cell.data_type == 'e' or calculated_cell.data_type == 'e'))
                    yield row
            sheets.append(Sheet(sheet.title, _bounded(rows())))
        return sheets
    finally:
        book.close()
        if cached is not None:
            cached.close()


def _read_xls(path):
    import xlrd
    book = xlrd.open_workbook(str(path), on_demand=True, formatting_info=True)
    try:
        sheets = []
        for sheet in book.sheets():
            if sheet.nrows > MAX_ROWS or sheet.ncols > MAX_COLUMNS:
                raise UploadError('WORKBOOK_LIMIT_EXCEEDED')
            def rows():
                for row_index in range(sheet.nrows):
                    row = []
                    for cell in sheet.row(row_index):
                        value = cell.value
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate_as_datetime(value, book.datemode)
                        fmt = book.format_map.get(book.xf_list[cell.xf_index].format_key)
                        row.append(make_cell(value, fmt.format_str if fmt else '', error=cell.ctype == xlrd.XL_CELL_ERROR))
                    yield row
            sheets.append(Sheet(sheet.name, _bounded(rows())))
        return sheets
    finally:
        book.release_resources()


def _read_csv(path):
    raw = path.read_bytes()
    text = None
    for encoding in ('utf-8-sig', 'utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'cp949'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    if text is None:
        raise UploadError('CSV_ENCODING_FAILED')
    try:
        dialect = csv.Sniffer().sniff(text[:16384], delimiters=',\t;|')
    except csv.Error:
        dialect = csv.excel
    return [Sheet(path.stem, _bounded([make_cell(value) for value in row]
                                    for row in csv.reader(io.StringIO(text), dialect, strict=True)))]


def read_sheets(path):
    path = Path(path)
    if path.suffix.casefold() not in ('.xlsx', '.xls', '.csv'):
        raise UploadError('UNSUPPORTED_EXTENSION')
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise UploadError('FILE_TOO_LARGE')
        sheets = {'.xlsx': _read_xlsx, '.xls': _read_xls, '.csv': _read_csv}[path.suffix.casefold()](path)
        if sum(sum(len(row) for row in s.rows) for s in sheets) > MAX_CELLS:
            raise UploadError('WORKBOOK_LIMIT_EXCEEDED')
        return sheets
    except UploadError:
        raise
    except ImportError:
        raise UploadError('READER_NOT_INSTALLED') from None
    except Exception:
        raise UploadError('FILE_READ_FAILED') from None


_DATE = re.compile(r'(?<!\d)(\d{4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})(?:일)?(?!\d)')


def dates(text):
    result = []
    for match in _DATE.finditer(text):
        try:
            result.append(date(*(int(v) for v in match.groups())).isoformat())
        except ValueError:
            pass
    return result


def amount_value(text, header=''):
    value = text.strip().replace(',', '').replace('₩', '').replace(' ', '')
    factor = Decimal(1)
    units = (('억원', 100000000), ('억', 100000000), ('천만원', 10000000), ('백만원', 1000000),
             ('십만원', 100000), ('만원', 10000), ('천원', 1000), ('원', 1))
    for unit, multiplier in units:
        if value.endswith(unit):
            value = value[:-len(unit)]
            factor = Decimal(multiplier)
            break
    else:
        for unit, multiplier in units:
            if unit in header:
                factor = Decimal(multiplier)
                break
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        return None
    try:
        return format(Decimal(value) * factor, 'f')
    except InvalidOperation:
        return None


def _year(text):
    match = re.fullmatch(r'\s*((?:19|20)\d{2})\s*년?\s*', text)
    return int(match[1]) if match else None


def _total(row):
    cells = [c.text.strip() for c in row if c.text.strip()]
    return bool(cells and normalize_header(cells[0]).rstrip(':：') in ('합계', '총계', '소계', 'total', 'grandtotal'))


def detect_header(rows):
    candidates = []
    for index, row in enumerate(rows[:60]):
        fields = {header_field(c.text) for c in row} - {None}
        nonempty = [c.text for c in row if c.text.strip()]
        density = sum(sum(bool(c.text.strip()) for c in r) >= 2 for r in rows[index+1:index+6])
        if len(nonempty) < 2:
            continue
        if len(fields) >= 2 or ('project_name' in fields and len(nonempty) >= 2):
            candidates.append((len(fields) * 10 + density, -index, index, False))
    if candidates:
        _, _, index, uncertain = max(candidates)
        return index, uncertain
    # Unknown but plausible header: retain all data with an explicit review flag.
    for index, row in enumerate(rows[:60]):
        values = [c.text.strip() for c in row if c.text.strip()]
        if (len(values) >= 2 and all(len(v) <= 24 and not dates(v) and not v.isdigit() for v in values)
                and any(sum(bool(c.text.strip()) for c in r) >= 2 for r in rows[index+1:index+4])):
            return index, True
    return None, True


def infer_columns(headers, rows):
    mapping = {i: header_field(h) for i, h in enumerate(headers) if header_field(h)}
    inferred = set()
    used = set(mapping.values())
    candidates = {}
    for index, header in enumerate(headers):
        if index in mapping or normalize_header(header) in ('no', '번호', '순번'):
            continue
        values = [r[index].text.strip() for r in rows[:200] if index < len(r) and r[index].text.strip()]
        if len(values) < 2:
            continue
        def ratio(predicate):
            return sum(bool(predicate(v)) for v in values) / len(values)
        field_name = None
        if ratio(_year) >= .9:
            field_name = 'year'
        elif ratio(lambda v: dates(v)) >= .9:
            field_name = 'date_candidate'
        elif ratio(lambda v: amount_value(v) is not None and bool(re.search(r'원|억|,|₩', v))) >= .8:
            field_name = 'amount'
        elif ratio(lambda v: bool(re.fullmatch(r'(?:[A-Za-z]+[-_/]?\d[\w/-]*|0\d{3,})', v))) >= .9:
            field_name = 'management_id'
        elif sum(len(v) for v in values)/len(values) >= 45:
            field_name = 'description'
        elif ratio(lambda v: len(v) <= 45 and bool(re.search(r'㈜|\(주\)|주식회사|진흥원|대학교|연구원|센터|공사|공단|재단', v))) >= .8:
            field_name = 'client'
        if field_name and field_name not in used:
            candidates.setdefault(field_name, []).append(index)
    for field_name, columns in candidates.items():
        if len(columns) == 1:
            mapping[columns[0]] = field_name
            inferred.add(columns[0])
    return mapping, inferred


@dataclass
class UploadRow:
    sheet: str
    row_number: int
    management_id: str | None
    project_name: str | None
    client: str | None
    start_date: str | None
    end_date: str | None
    year: int | None
    technical_field: str
    work_type: str
    description: str
    keywords: tuple[str, ...]
    amount: str | None
    raw_source: dict
    searchable_text: str
    match_text: str
    fingerprint: str
    issues: list[str] = field(default_factory=list)
    field_sources: dict = field(default_factory=dict)
    field_confidence: dict = field(default_factory=dict)
    ai_model_version: str | None = None
    normalization_version: str = 'performance-normalization-2'
    review_required: bool = False
    technical_fields: list = field(default_factory=list)
    ai_evidence: dict = field(default_factory=dict)
    performance_id: str | None = None
    base_revision: str | None = None
    user_edits: set = field(default_factory=set)
    technical_tags: list = field(default_factory=list)

    @property
    def status(self):
        if self.issues and all(issue.startswith('로컬 AI ') and issue.endswith('확인 권장') for issue in self.issues):
            return '확인 권장'
        return '확인 필요' if self.issues or self.review_required else '정상'


@dataclass
class UploadPreview:
    filename: str
    sheet_count: int
    rows: list[UploadRow]
    excluded: int
    warnings: list[str]
    mappings: dict
    analysis_stats: dict = field(default_factory=dict)

    @property
    def review_count(self):
        return sum(bool(r.issues) or r.review_required for r in self.rows)


def normalize_row(sheet, row_number, headers, cells, mapping, inferred, header_uncertain):
    raw = {header: (cells[i].formula or cells[i].value) if i < len(cells) else None
           for i, header in enumerate(headers)}
    formats = {headers[i]: cell.number_format for i, cell in enumerate(cells)
               if i < len(headers) and cell.number_format and cell.number_format != 'General'}
    groups = {}
    for index, field_name in mapping.items():
        if index < len(cells) and cells[index].text.strip():
            groups.setdefault(field_name, []).append(cells[index].text.strip())
    def one(name):
        return groups.get(name, [''])[0]
    issues = ['header 매핑 확인 필요'] if header_uncertain else []
    issues += [f'{mapping[i]} 매핑 확인 필요' for i in sorted(inferred) if i < len(cells) and cells[i].text.strip()]
    issues += [f'미분류 열: {headers[i]} 확인 필요' for i, c in enumerate(cells)
               if c.text.strip() and i not in mapping and normalize_header(headers[i]) not in ('no', '번호', '순번')]
    for key in ('management_id', 'project_name', 'client', 'year', 'start_date', 'end_date', 'amount'):
        if len(set(groups.get(key, []))) > 1:
            issues.append(f'{key} 복수 열 확인 필요')
    for cell in cells:
        if cell.formula and not cell.text:
            issues.append('수식 계산값 없음: 원본 수식 보존')
        if cell.error:
            issues.append('셀 오류 확인 필요')
    start = dates(one('start_date'))
    end = dates(one('end_date'))
    period = dates(one('period'))
    start_date = start[0] if start else (period[0] if len(period) >= 2 else None)
    end_date = end[0] if end else (period[-1] if len(period) >= 2 else None)
    year = _year(one('year'))
    if one('year') and year is None:
        issues.append('year 값 확인 필요')
    for name, parsed in (('start_date', start_date), ('end_date', end_date)):
        if one(name) and not parsed:
            issues.append(f'{name} 값 확인 필요')
    if start_date and end_date and start_date > end_date:
        issues.append('시작일/종료일 순서 확인 필요')
    if year is None:
        candidate = start_date or end_date or next(iter(dates(one('date_candidate'))), None)
        year = int(candidate[:4]) if candidate else None
    amount_col = next((headers[i] for i, f in mapping.items() if f == 'amount'), '')
    amount = amount_value(one('amount'), amount_col) if one('amount') else None
    if one('amount') and amount is None:
        issues.append('amount 값 확인 필요')
    project_name = one('project_name') or None
    if project_name is None:
        issues.append('project_name 매핑 확인 필요')
    # Include every original cell in searchable_text; remove code/currency/date
    # columns from the adapter's description to avoid irrelevant matcher points.
    texts = [c.text for c in cells if c.text.strip()]
    match_texts = []
    for index, cell in enumerate(cells):
        value = cell.text.strip()
        if (not value or cell.error or mapping.get(index) in ('management_id', 'amount', 'year', 'start_date', 'end_date', 'period')
                or re.fullmatch(r'[\d\W_]+', value) or dates(value)
                or re.fullmatch(r'[A-Za-z]{1,8}[-_/]\d[\w/-]*', value)):
            continue
        match_texts.append(value)
    description = '\n'.join(groups.get('description', []))
    keywords = tuple(dict.fromkeys(w.strip() for v in groups.get('keywords', []) for w in re.split(r'[,;|\n]', v) if w.strip()))
    fingerprint_data = sorted((mapping.get(i, normalize_header(headers[i])), canonical(c.formula or c.text))
                              for i, c in enumerate(cells) if c.text.strip() or c.formula)
    fingerprint = sha256(json.dumps(fingerprint_data, ensure_ascii=False).encode()).hexdigest()
    # Preserve format information without overwriting any original header keys.
    raw_source = {'columns': raw, 'number_formats': formats}
    result = UploadRow(sheet, row_number, one('management_id') or None, project_name, one('client') or None,
                     start_date, end_date, year, one('technical_field'), one('work_type'), description,
                     keywords, amount, raw_source, '\n'.join(texts), '\n'.join(dict.fromkeys(match_texts)),
                     fingerprint, list(dict.fromkeys(issues)))
    for name in ('management_id', 'project_name', 'client', 'start_date', 'end_date', 'year',
                 'technical_field', 'work_type', 'description', 'keywords', 'amount'):
        columns = [i for i, mapped in mapping.items() if mapped == name and i < len(cells) and cells[i].text.strip()]
        value = getattr(result, name)
        if value not in (None, '', ()) and columns:
            if any(i in inferred for i in columns):
                source, confidence = 'deterministic_heuristic', None
            else:
                source = 'excel_header' if normalize_header(headers[columns[0]]) in (
                    normalize_header(name), normalize_header(ALIASES[name][0])) else 'header_alias'
                confidence = 1.0
        elif value not in (None, '', ()):
            source, confidence = 'deterministic_parser', 1.0
        else:
            source, confidence = 'unknown', None
        result.field_sources[name], result.field_confidence[name] = source, confidence
    result.review_required = bool(result.issues)
    return result


def preview_upload(path):
    sheets = read_sheets(path)
    rows, excluded, warnings, mappings = [], 0, [], {}
    nonempty_sheets = 0
    for sheet in sheets:
        if not any(c.text.strip() or c.formula for r in sheet.rows for c in r):
            continue
        nonempty_sheets += 1
        index, uncertain = detect_header(sheet.rows)
        if index is None:
            warnings.append(f'{sheet.name}: header 탐색 실패')
            excluded += sum(any(c.text.strip() or c.formula for c in r) for r in sheet.rows)
            continue
        width = max(len(r) for r in sheet.rows)
        header_cells = sheet.rows[index]
        headers, used = [], set()
        for i in range(width):
            name = header_cells[i].text.strip() if i < len(header_cells) else ''
            name = name or f'열 {i+1}'
            if name in used:
                name = f'{name} [열 {i+1}]'
            while name in used:
                name += '_'
            used.add(name)
            headers.append(name)
        mapping, inferred = infer_columns(headers, sheet.rows[index+1:])
        mappings[sheet.name] = {headers[i]: {'field': field_name, 'method': 'heuristic' if i in inferred else 'header'}
                                for i, field_name in mapping.items()}
        for row_index, cells in enumerate(sheet.rows[index+1:], start=index+2):
            if not any(c.text.strip() or c.formula for c in cells):
                continue
            if _total(cells) or [c.text for c in cells] == [c.text for c in header_cells]:
                excluded += 1
                continue
            rows.append(normalize_row(sheet.name, row_index, headers, cells, mapping, inferred, uncertain))
    if not nonempty_sheets:
        raise UploadError('NO_SHEET_DATA')
    if not rows:
        raise UploadError('HEADER_NOT_FOUND' if warnings else 'NO_VALID_ROWS')
    return UploadPreview(Path(path).name, nonempty_sheets, rows, excluded, warnings, mappings)
