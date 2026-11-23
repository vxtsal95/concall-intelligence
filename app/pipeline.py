import asyncio, logging, re
from pathlib import Path
from . import db
from .config import RAW, PROCESSED, POLL_INTERVAL, MAX_PDF_MB, NSE_ENABLED, BSE_ENABLED
from .ingest import ExchangeClient, download_pdf
from .extract import extract_pdf
from .summarize import summarize, to_markdown

log=logging.getLogger(__name__)
EVENTS=None

def set_event_queue(queue):
    global EVENTS; EVENTS=queue

def process_one(filing_id):
    row=db.get_filing(filing_id)
    if not row: return
    try:
        safe=re.sub(r'[^A-Za-z0-9_-]+','_',row['symbol'] or row['company'] or f"filing_{filing_id}")[:60]
        pdf=RAW/f"{filing_id}_{safe}.pdf"
        download_pdf(row['source_url'],pdf,MAX_PDF_MB)
        db.update_filing(filing_id,pdf_path=str(pdf),status='extracting',error=None)
        text=extract_pdf(pdf)
        (PROCESSED/f'{filing_id}_{safe}.txt').write_text(text,encoding='utf-8')
        metadata={'company':row['company'],'scrip_code':row['scrip_code'],'nse_symbol':row['symbol'],'quarter':row['quarter'],'call_date':row['filing_date'],'source':row['exchange'],'source_url':row['source_url']}
        db.update_filing(filing_id,status='summarizing')
        payload=summarize(text,metadata)
        markdown=to_markdown(payload)
        (PROCESSED/f'{filing_id}_{safe}.json').write_text(__import__('json').dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
        (PROCESSED/f'{filing_id}_{safe}.md').write_text(markdown,encoding='utf-8')
        db.save_summary(filing_id,payload,markdown)
        return {'id':filing_id,'payload':payload,'markdown':markdown}
    except Exception as e:
        log.exception('Processing failed for filing %s',filing_id)
        db.update_filing(filing_id,status='failed',error=str(e)[:1000])
        return None

async def watch_loop():
    db.init_db(); client=ExchangeClient()
    while True:
        try:
            # Exchange toggles are kept in configuration for deployments that need one source disabled.
            discovered=client.discover()
            for item in discovered:
                if (item['exchange']=='NSE' and not NSE_ENABLED) or (item['exchange']=='BSE' and not BSE_ENABLED): continue
                if db.add_filing(item):
                    rows=db.list_filings(); match=next((r for r in rows if r['dedupe_key']==item['dedupe_key']),None)
                    if match:
                        result=await asyncio.to_thread(process_one,match['id'])
                        if result and EVENTS:
                            await EVENTS.put({'type':'new_summary',**result})
        except Exception: log.exception('Watcher cycle failed')
        await asyncio.sleep(POLL_INTERVAL)
