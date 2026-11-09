"""Explicit metadata-only public-session diagnostic. No file download or AI."""
import argparse,json,time
from pathlib import Path
from src.scrapers.exportvoucher_notice import ExportVoucherSession,notice_url

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=[]
    shared=ExportVoucherSession()
    for mode in ('shared','fresh'):
        for identity in ('13038','8410','13034'):
            session=shared if mode=='shared' else ExportVoucherSession()
            row=dict(mode=mode,notice_id=identity)
            try:
                html=session.get(notice_url(identity),timeout=25,headers={'User-Agent':'NoticeMonitor/0.1'})
                row['detail']='SUCCESS'
                files=session.list_attachments(html)
                row.update(status='SUCCESS',files=[dict(file_id=f.file_id,name=f.name,size=f.size) for f in files])
            except Exception as e:
                row.update(status='FAILED',error_type=type(e).__name__,error=str(e))
            rows.append(row)
            time.sleep(2)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=True,indent=2))
if __name__=='__main__': main()
