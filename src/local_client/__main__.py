"""Separate local entry point: python -m src.local_client --base-url URL."""

import argparse

from .sync import FeedClient, SyncError


def main(argv=None):
    parser = argparse.ArgumentParser(description='Download public notice feed with last-good local cache (M12).')
    parser.add_argument('--base-url', required=True, help='Published directory containing both public JSON files')
    parser.add_argument('--cache-dir', default=None, help='Default: project local/cache')
    parser.add_argument('--timeout', type=float, default=30, help='Per-request timeout in seconds (default: 30)')
    args = parser.parse_args(argv)
    try:
        result = FeedClient(args.base_url, cache_dir=args.cache_dir, timeout=args.timeout).sync()
    except SyncError as error:
        print(f'SYNC ERROR: {error.code}; no valid cache available')
        return 2
    print(f'SYNC {result.status}: notices={result.metadata["notice_count"]} '
          f'generated_at={result.metadata["generated_at"]}'
          + (f' error={result.error_code}' if result.error_code else ''))
    return 1 if result.status == 'FALLBACK' else 0


if __name__ == '__main__':
    raise SystemExit(main())
