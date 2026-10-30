"""M10 central command; preflight configuration before external requests."""

import argparse
import os

from src.ai.gemini import GeminiClient, GeminiError
from src.core.diff import DiffInputError
from src.core.storage import JsonStorage, StorageError
from src.pipeline import CONFIG_PATH, PipelineConfigError, load_site_configs, run_pipeline
from src.renderer.feed import FeedInputError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Run the central notice pipeline (M10).')
    parser.add_argument('--config', default=CONFIG_PATH, help='JSON-syntax sites.yaml path')
    parser.add_argument('--data-dir', default=None, help='Storage directory (default: project data)')
    parser.add_argument('--public-dir', default=None, help='Feed directory (default: project public)')
    args = parser.parse_args(argv)
    try:
        configs = load_site_configs(args.config)
        if not any(config.get('enabled', False) for config in configs):
            raise PipelineConfigError('NO_ENABLED_SITES: enable an implemented source in sites.yaml')
        if not os.environ.get('GEMINI_API_KEY', '').strip() or not os.environ.get('GEMINI_MODEL', '').strip():
            raise PipelineConfigError('MISSING_GEMINI_CONFIG: set GEMINI_API_KEY and GEMINI_MODEL in process environment')
        result = run_pipeline(client=GeminiClient(), config_path=args.config,
                              storage=JsonStorage(args.data_dir), public_dir=args.public_dir)
    except (PipelineConfigError, GeminiError) as error:
        print(f'CONFIGURATION ERROR: {error}')
        return 2
    except (StorageError, DiffInputError, FeedInputError):
        print('PIPELINE ERROR: storage, diff or feed validation/write failed; existing files are not reset')
        return 2
    except Exception:
        # Do not print unexpected raw errors: they can contain secret values.
        print('PIPELINE ERROR: unexpected failure; inspect configuration and local data')
        return 2
    counts = {status: sum(n.status.value == status for n in result.observed)
              for status in ('NEW', 'UPDATED', 'EXISTING')}
    print(f'PIPELINE {"PARTIAL" if result.degraded else "PASS"}: '
          f'NEW={counts["NEW"]} UPDATED={counts["UPDATED"]} EXISTING={counts["EXISTING"]} '
          f'stored={len(result.notices)} feed={result.feed_count} '
          f'scraper_failures={len(result.scraper_failures)} analysis_failures={len(result.analysis_failures)}')
    return 1 if result.degraded else 0


if __name__ == "__main__":
    raise SystemExit(main())
