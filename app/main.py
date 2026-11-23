import asyncio, json, logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from . import db
from .pipeline import watch_loop, set_event_queue
from .config import ROOT, RAW, PROCESSED

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
queue=asyncio.Queue()
@asynccontextmanager
async def lifespan(app):
    db.init_db(); set_event_queue(queue)
    task=asyncio.create_task(watch_loop())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
app=FastAPI(title='Concall Intelligence Pipeline',version='1.0.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@app.get('/',response_class=HTMLResponse)
def home(): return (ROOT/'static'/'index.html').read_text(encoding='utf-8')
@app.get('/api/filings')
def filings():
    rows=db.list_filings()
    for r in rows:
        if r.get('payload'): r['payload']=json.loads(r['payload'])
    return rows
@app.get('/api/filings/{filing_id}/transcript')
def transcript(filing_id:int):
    row=db.get_filing(filing_id)
    if not row or not row['pdf_path']: return JSONResponse({'error':'Transcript not available'},404)
    return FileResponse(row['pdf_path'],media_type='application/pdf',filename=Path(row['pdf_path']).name)
@app.websocket('/ws')
async def websocket_endpoint(ws:WebSocket):
    await ws.accept()
    try:
        await ws.send_json({'type':'connected','message':'Connected to live concall feed'})
        while True:
            event=await queue.get(); await ws.send_json(event)
    except WebSocketDisconnect: pass
