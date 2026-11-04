"""Build-time only model acquisition; never imported by the desktop runtime."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen, Request

REPO = 'intfloat/multilingual-e5-small'
PINNED_REVISION = '614241f622f53c4eeff9890bdc4f31cfecc418b3'
ROOT = Path(__file__).resolve().parents[1]/'resources/models/performance_classifier'
FILES = ('onnx/model_qint8_avx512_vnni.onnx', 'tokenizer.json', 'tokenizer_config.json', 'config.json', 'README.md')


def request(url):
    return urlopen(Request(url, headers={'User-Agent': 'NoticeCrawling-Build/1.0'}), timeout=90)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('inspect', 'download'))
    args = parser.parse_args()
    with request(f'https://huggingface.co/api/models/{REPO}?blobs=true') as response:
        info = json.load(response)
    if info.get('cardData', {}).get('license') != 'mit':
        raise RuntimeError('MODEL_LICENSE_CHANGED')
    revision = info['sha']
    if revision != PINNED_REVISION:
        raise RuntimeError('MODEL_REVISION_CHANGED_REVIEW_REQUIRED')
    files = {item['rfilename']: item for item in info['siblings']}
    summary = dict(repo=REPO, revision=revision, license='mit', files={name: files.get(name, {}).get('size') for name in FILES},
                   onnx_files={name: item.get('size') for name, item in files.items() if name.endswith('.onnx')})
    print(json.dumps(summary))
    if args.command == 'inspect':
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    records = {}
    for name in FILES:
        filename = 'model.onnx' if name.startswith('onnx/') else name
        path = ROOT/filename
        expected = files[name].get('lfs', {}).get('sha256')
        if path.exists() and expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            pass
        else:
            temporary = path.with_suffix(path.suffix+'.download')
            with request(f'https://huggingface.co/{REPO}/resolve/{revision}/{name}?download=true') as response, temporary.open('wb') as output:
                while chunk := response.read(1024*1024):
                    output.write(chunk)
            if expected and hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise RuntimeError('MODEL_HASH_MISMATCH')
            temporary.replace(path)
        records[filename] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with request('https://raw.githubusercontent.com/microsoft/unilm/master/LICENSE') as response:
        license_text = response.read()
    (ROOT/'LICENSE-MIT.txt').write_bytes(license_text)
    notices = ROOT/'notices'
    notices.mkdir(exist_ok=True)
    for filename, url in (
        ('tokenizers-LICENSE.txt', 'https://raw.githubusercontent.com/huggingface/tokenizers/v0.22.2/LICENSE'),
        ('flatbuffers-LICENSE.txt', 'https://raw.githubusercontent.com/google/flatbuffers/master/LICENSE')):
        with request(url) as response:
            (notices/filename).write_bytes(response.read())
    manifest = {**summary, 'artifacts': records, 'model_version': f'{REPO}@{revision}:qint8',
                'license_source': 'https://github.com/microsoft/unilm/blob/master/LICENSE'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('MODEL_RESOURCE_BYTES='+str(sum(p.stat().st_size for p in ROOT.iterdir() if p.is_file())))


if __name__ == '__main__':
    main()
