"""Short-lived parser process; caller imposes a hard CPU/wall-time boundary."""
import json
import sys
from pathlib import Path
from src.core.extraction import Extractor, failure


def main():
    root = Path(sys.argv[1])
    options = json.loads((root/'options.json').read_text(encoding='utf-8'))
    extractor = Extractor(options['cache'],budget_seconds=options['budget'],pages_per_run=options['pages'])
    try:
        result = extractor.document((root/'input').read_bytes(),options['name'],options['kind'])
    except Exception as error:
        result = dict(failure(error),parts=[])
    (root/'result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':
    main()
