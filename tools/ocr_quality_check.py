"""Reproducible real Korean poster/scan validation (public sources only)."""
import argparse
import io
import json
import re
import subprocess
import time
from pathlib import Path

from src.core.extraction import Extractor, Resource, download


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker-image')
    parser.add_argument('--output', default='.run/ocr-quality')
    args = parser.parse_args()
    from PIL import Image, ImageDraw, ImageFont
    import pymupdf
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    def engine(data):
        result = subprocess.run(['docker','run','--rm','-i', args.docker_image,
            'stdin','stdout','-l','kor+eng','--psm','6'],input=data,capture_output=True,timeout=60,check=True)
        return result.stdout.decode('utf-8').strip()
    extractor = Extractor(root/'cache', ocr=engine if args.docker_image else None)
    resource = Resource('https://www.khidi.or.kr/resources/component/crosseditor/binary/images/images/000285/aW1hZ2U=_34.png', kind='image')
    data, _ = download(resource)
    (root/'official-poster.png').write_bytes(data)
    started = time.monotonic()
    poster = extractor.document(data,'official-poster.png','image')
    image = Image.open(io.BytesIO(data)).convert('RGB')
    jpeg = io.BytesIO(); image.save(jpeg, format='JPEG', quality=95)
    jpg = extractor.document(jpeg.getvalue(),'poster.jpg','image')
    # Same real notice image inside a scan PDF tests rendering/extraction.
    doc = pymupdf.open(); page=doc.new_page(width=image.width,height=image.height)
    page.insert_image(page.rect,stream=data)
    scan = doc.tobytes(); doc.close()
    (root/'official-scan.pdf').write_bytes(scan)
    pdf = extractor.document(scan,'official-scan.pdf')
    import zipfile
    hwpx = io.BytesIO()
    with zipfile.ZipFile(hwpx,'w') as z:
        z.writestr('Contents/section0.xml','<root><t>원문 텍스트 참가 자격</t></root>')
        z.writestr('BinData/poster.png', data)
    hwp = extractor.document(hwpx.getvalue(),'poster.hwpx')
    # An explicit gold phrase checks Korean duty and eligibility recognition.
    font_paths = ['C:/Windows/Fonts/malgun.ttf','/usr/share/fonts/truetype/nanum/NanumGothic.ttf']
    font = ImageFont.truetype(next(p for p in font_paths if Path(p).exists()),42)
    sample=Image.new('RGB',(1500,500),'white'); draw=ImageDraw.Draw(sample)
    draw.multiline_text((50,60),'특허분석 수행기관 모집\n수행 업무: 선행기술조사 및 특허분석\n참가 자격: 특허법인 또는 변리사\n마감일: 2026.11.20',font=font,fill='black',spacing=30)
    output=io.BytesIO();sample.save(output,format='PNG')
    (root/'gold-korean.png').write_bytes(output.getvalue())
    gold=extractor.document(output.getvalue(),'gold.png','image')
    results = dict(poster=poster,jpg=jpg,scan_pdf=pdf,hwpx=hwp,gold=gold)
    for file_id, extension in ((1,'pdf'),(2,'hwp')):
        url=f'https://www.khidi.or.kr/fileDownload?titleId=534636&fileId={file_id}&fileDownType=C&paramMenuId=MENU01108'
        binary, filename=download(Resource(url))
        (root/f'official-attachment.{extension}').write_bytes(binary)
        results['official_'+extension]=extractor.document(binary,filename or 'notice.'+extension)
    text=' '.join(p.get('text','') for p in gold['parts'])
    report = dict(engine='Tesseract kor+eng',elapsed_seconds=round(time.monotonic()-started,3),
                  status={k:v['status'] for k,v in results.items()},
                  characters={k:sum(len(p.get('text','')) for p in v['parts']) for k,v in results.items()},
                  gold_duty='특허분석수행기관모집' in re.sub(r'\s+','',text),
                  gold_qualification='특허법인' in text and '변리사' in text)
    (root/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if all(v=='SUCCESS' for v in report['status'].values()) and report['gold_duty'] and report['gold_qualification'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
