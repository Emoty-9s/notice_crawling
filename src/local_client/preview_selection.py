"""Transient preview selection, never serialized to performance business data."""
from dataclasses import asdict, dataclass, replace
from .upload import UploadError
from .upload_store import ImportResult, save_preview, save_enriched_preview


class PreviewSelection:
    def __init__(self, count=0):
        self.count = count
        self.checked = set(range(count))

    def toggle(self, index):
        if type(index) is not int or not 0 <= index < self.count:
            raise ValueError('INVALID_PREVIEW_INDEX')
        self.checked.symmetric_difference_update({index})

    def set_all(self, checked):
        self.checked = set(range(self.count)) if checked else set()

    def invert(self):
        self.checked = set(range(self.count))-self.checked


@dataclass(frozen=True)
class SelectedImportResult(ImportResult):
    selected: int = 0
    excluded_by_user: int = 0


def save_selected(database, preview, checked, *, existing=False):
    indexes = set(checked)
    if any(type(i) is not int or not 0 <= i < len(preview.rows) for i in indexes):
        raise ValueError('INVALID_PREVIEW_INDEX')
    if not indexes:
        raise UploadError('NO_SELECTED_ROWS')
    # Only this detached subset reaches either persistence entry point.
    subset = replace(preview, rows=[row for i,row in enumerate(preview.rows) if i in indexes])
    saver = save_enriched_preview if existing else save_preview
    result = saver(database, subset)
    return SelectedImportResult(**asdict(result), selected=len(indexes), excluded_by_user=len(preview.rows)-len(indexes))
