"""Exchange adapters. Endpoints and response formats can change; failures are isolated per source."""
import hashlib, logging, re, time
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from .config import TIMEOUT, WATCH_SYMBOLS

log = logging.getLogger(__name__)
TRANSCRIPT_WORDS = re.compile(r'\b(transcript|earnings call transcript|conference call transcript|concall transcript)\b', re.I)
NON_TRANSCRIPT = re.compile(r'\b(audio recording|audio link|investor presentation|intimation of earnings call|schedule of analyst)\b', re.I)

class ExchangeClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36','Accept':'application/json, text/plain, */*','Accept-Language':'en-US,en;q=0.9','Referer':'https://www.nseindia.com/'})

    def nse(self):
        # NSE requires a landing-page session before its JSON endpoint.
        try:
            self.s.get('https://www.nseindia.com/', timeout=TIMEOUT)
            end = datetime.now(); start = end - timedelta(days=10)
            url = 'https://www.nseindia.com/api/corporate-announcements'
            params = {'index':'equities','from_date':start.strftime('%d-%m-%Y'),'to_date':end.strftime('%d-%m-%Y')}
            r = self.s.get(url, params=params, timeout=TIMEOUT); r.raise_for_status()
            data = r.json()
            return [self._normalise_nse(x) for x in data if isinstance(x, dict)]
        except Exception as e:
            log.warning('NSE fetch failed: %s', e); return []

    def _normalise_nse(self, x):
        title = str(x.get('desc') or x.get('subject') or x.get('sm_name') or '')
        symbol = str(x.get('symbol') or '').upper()
        attachment = x.get('attchmntFile') or x.get('attachment') or x.get('fileName') or ''
        url = urljoin('https://www.nseindia.com', str(attachment)) if attachment else ''
        return {'exchange':'NSE','company':x.get('sm_name') or x.get('companyName') or symbol,'symbol':symbol,'scrip_code':str(x.get('sm_isin') or ''),'filing_date':str(x.get('an_dt') or x.get('date') or '')[:10], 'title':title,'source_url':url,'quarter':self._quarter(title)}

    def bse(self):
        # BSE endpoint is intentionally isolated: BSE occasionally changes parameter names / response shape.
        try:
            url='https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w'
            params={'strCat':'Company Update','strPrevDate':(datetime.now()-timedelta(days=10)).strftime('%Y%m%d'),'strScrip':'','strSearch':'','strToDate':datetime.now().strftime('%Y%m%d'),'strType':'C','subcategory':'',' scripcode':''}
            headers={'Referer':'https://www.bseindia.com/','Origin':'https://www.bseindia.com'}
            r=self.s.get(url,params=params,headers=headers,timeout=TIMEOUT); r.raise_for_status(); data=r.json()
            rows=data if isinstance(data,list) else data.get('Table', data.get('data', []))
            out=[]
            for x in rows:
                title=str(x.get('NEWSSUB') or x.get('HEADLINE') or x.get('NEWS_DT') or '')
                code=str(x.get('SCRIP_CD') or x.get('scrip_cd') or '')
                attachment=x.get('ATTACHMENTNAME') or x.get('ATTACHMENT') or ''
                url=urljoin('https://www.bseindia.com',str(attachment)) if attachment else ''
                out.append({'exchange':'BSE','company':x.get('SLONGNAME') or x.get('LONG_NAME') or '', 'symbol':'','scrip_code':code,'filing_date':str(x.get('NEWS_DT') or '')[:10],'title':title,'source_url':url,'quarter':self._quarter(title)})
            return out
        except Exception as e:
            log.warning('BSE fetch failed: %s',e); return []

    @staticmethod
    def _quarter(title):
        m=re.search(r'Q\s*([1-4])\s*(?:FY)?\s*(20?\d{2})',title,re.I)
        return f'Q{m.group(1)} FY{m.group(2)[-2:]}' if m else None

    @staticmethod
    def is_transcript(item):
        title=item.get('title','')
        if not TRANSCRIPT_WORDS.search(title) or NON_TRANSCRIPT.search(title): return False
        return bool(item.get('source_url'))

    @staticmethod
    def dedupe_key(item):
        # Same PDF mirrored on NSE/BSE is deduped by normalized URL; fallback to company/title/date.
        identity=(item.get('source_url') or '').split('?')[0].lower()
        if not identity: identity='|'.join(str(item.get(k) or '') for k in ('company','title','filing_date')).lower()
        return hashlib.sha256(identity.encode()).hexdigest()

    def discover(self):
        items=[]
        items += self.nse()
        time.sleep(1.0) # polite pause between exchanges
        items += self.bse()
        result=[]
        for x in items:
            if not self.is_transcript(x): continue
            if WATCH_SYMBOLS and x.get('symbol') and x['symbol'] not in WATCH_SYMBOLS: continue
            x['dedupe_key']=self.dedupe_key(x); result.append(x)
        return result

def download_pdf(url, destination, max_mb=80):
    if not url.startswith('https://'): raise ValueError('Refusing non-HTTPS attachment URL')
    headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.nseindia.com/'}
    with requests.get(url,headers=headers,stream=True,timeout=TIMEOUT) as r:
        r.raise_for_status(); ctype=r.headers.get('Content-Type','').lower()
        if 'pdf' not in ctype and not url.lower().endswith('.pdf'):
            # Some exchanges use generic octet-stream; validate magic bytes below.
            pass
        total=0; first=b''
        with open(destination,'wb') as f:
            for chunk in r.iter_content(1024*64):
                if not chunk: continue
                if len(first)<5: first += chunk[:5-len(first)]
                total += len(chunk)
                if total > max_mb*1024*1024: raise ValueError('PDF exceeds configured size limit')
                f.write(chunk)
    if not first.startswith(b'%PDF-'):
        destination.unlink(missing_ok=True); raise ValueError('Attachment response is not a PDF')
    return destination
