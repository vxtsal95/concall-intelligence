import re
import fitz

def extract_pdf(path):
    doc=fitz.open(path); pages=[]
    for i,page in enumerate(doc):
        text=page.get_text('text', sort=True)
        text=text.replace('\u00a0',' ')
        lines=[]
        for line in text.splitlines():
            line=re.sub(r'\s+',' ',line).strip()
            if not line: continue
            if re.fullmatch(r'(page\s*)?\d+(\s*of\s*\d+)?',line,re.I): continue
            if re.search(r'www\.|investor relations|registered office|corporate office',line,re.I) and len(line)<110: continue
            lines.append(line)
        pages.append('\n'.join(lines))
    full='\n\n'.join(p for p in pages if p)
    full=re.sub(r'\n{3,}','\n\n',full)
    if len(full.strip()) < 300:
        # Optional OCR fallback for image-only/scanned PDFs.
        try:
            import pytesseract
            from PIL import Image
            import io
            ocr=[]
            for page in doc:
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                ocr.append(pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes('png')))))
            full='\n\n'.join(ocr)
        except Exception:
            pass
    if len(full.strip()) < 100: raise ValueError('No usable transcript text extracted; PDF may be scanned or malformed (check Tesseract installation).')
    return full

def chunk_text(text, max_chars=14000, overlap=800):
    # Prefer paragraph boundaries; overlap preserves context across chunk edges.
    paras=[p.strip() for p in text.split('\n\n') if p.strip()]
    chunks=[]; current=''
    for p in paras:
        if len(current)+len(p)+2 <= max_chars:
            current=(current+'\n\n'+p).strip(); continue
        if current: chunks.append(current)
        if len(p)>max_chars:
            start=0
            while start<len(p):
                end=min(len(p),start+max_chars); chunks.append(p[start:end]); start=max(start+max_chars-overlap,start+1)
            current=''
        else: current=p
    if current: chunks.append(current)
    return chunks
