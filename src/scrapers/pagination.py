"""One bounded newest-page collection policy for every active source."""
MAX_COLLECTION_PAGES = 3


def collection_pages(config):
    requested = config.get('max_pages', MAX_COLLECTION_PAGES)
    if type(requested) is not int or requested < 1:
        raise ValueError('max_pages must be a positive integer')
    return min(requested, MAX_COLLECTION_PAGES)
