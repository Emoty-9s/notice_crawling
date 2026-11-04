"""Offline build preflight and third-party license notices. No model inference."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'resources/models/performance_classifier'


def main():
    manifest = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['license'] == 'mit', 'MODEL_LICENSE_MISSING'
    assert (ROOT/'LICENSE-MIT.txt').is_file(), 'MODEL_LICENSE_MISSING'
    assert (ROOT/'taxonomy.json').is_file(), 'MODEL_TAXONOMY_MISSING'
    for name, artifact in manifest['artifacts'].items():
        with (ROOT/name).open('rb') as source:
            assert hashlib.file_digest(source, 'sha256').hexdigest() == artifact['sha256'], 'MODEL_HASH_MISMATCH'
    notices = ROOT/'notices'
    notices.mkdir(exist_ok=True)
    for package in ('onnxruntime', 'tokenizers', 'numpy', 'flatbuffers', 'protobuf', 'coloredlogs', 'humanfriendly', 'sympy', 'mpmath'):
        dist = importlib.metadata.distribution(package)
        found = False
        for item in dist.files or []:
            name = Path(str(item)).name
            if any(word in name.casefold() for word in ('license', 'notice', 'copying')) and Path(name).suffix.lower() in ('', '.txt', '.md'):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    target = notices/(package+'-'+hashlib.sha256(str(item).encode()).hexdigest()[:8]+'-'+name)
                    target.write_bytes(path.read_bytes())
                    found = True
        if not found and not (notices/(package+'-LICENSE.txt')).is_file():
            raise RuntimeError('PACKAGE_LICENSE_MISSING_'+package)
    print('OFFLINE_MODEL_RESOURCE_CHECK_PASS bytes='+str(sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())))


if __name__ == '__main__':
    main()
