import json, re
from openai import OpenAI
from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

SCHEMA={"company":"","scrip_code":"","nse_symbol":"","quarter":"","call_date":"","source":"","source_url":"","tldr":[],"management_commentary":[],"guidance":[],"segment_performance":[],"key_metrics":[],"notable_qa":[],"risks":[]}
SYSTEM='''You are a financial transcript analyst. Use ONLY evidence in the supplied transcript excerpts. Never infer missing values, never use outside knowledge, and never convert an aspiration into a committed target. If a field is not stated, return an empty array or empty string. Preserve units, periods, and qualifiers. Distinguish reported results from forward-looking guidance. For Q&A, include only questions and answers actually present. Output valid JSON only, matching the requested schema. Add a short evidence quote or page/chunk reference in each item when possible.'''

def _client():
    if not LLM_API_KEY: return None
    return OpenAI(api_key=LLM_API_KEY,base_url=LLM_BASE_URL)

def summarize(text, metadata):
    client=_client()
    if client is None: raise RuntimeError('LLM_API_KEY is not configured. Add it to .env to generate summaries.')
    from .extract import chunk_text
    chunks=chunk_text(text)
    partial=[]
    for i,ch in enumerate(chunks,1):
        prompt=f'''Summarize transcript chunk {i}/{len(chunks)} as evidence notes. Keep exact numbers and units. Do not invent missing information. Include management commentary, outlook, segments, metrics, Q&A, and risks.\n\nMETADATA: {json.dumps(metadata)}\n\nTRANSCRIPT CHUNK:\n{ch}'''
        r=client.chat.completions.create(model=LLM_MODEL,temperature=0.0,messages=[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}])
        partial.append(r.choices[0].message.content or '')
    # Final consolidation is constrained to extracted chunk notes, not model memory.
    prompt=f'''Consolidate the evidence notes below into this JSON schema exactly:\n{json.dumps(SCHEMA)}\n\nMetadata to populate where known: {json.dumps(metadata)}\n\nEvidence notes:\n{chr(10).join(partial)}\n\nReturn JSON only. Do not add facts. Use [] for unsupported list fields and "" for unsupported scalar fields.'''
    r=client.chat.completions.create(model=LLM_MODEL,temperature=0.0,response_format={'type':'json_object'},messages=[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}])
    payload=json.loads(r.choices[0].message.content)
    for key,val in SCHEMA.items(): payload.setdefault(key,val)
    return payload

def to_markdown(p):
    def bullets(items): return '\n'.join(f'- {x}' if isinstance(x,str) else '- '+json.dumps(x,ensure_ascii=False) for x in items) or '- Not stated in transcript.'
    out=[f"# {p.get('company') or 'Company'} — {p.get('quarter') or 'Earnings call'}",f"**Call date:** {p.get('call_date') or 'Not stated'}  ",f"**Source:** {p.get('source') or 'Not stated'}  ",f"**Source document:** {p.get('source_url') or 'Not available'}",'## TL;DR',bullets(p.get('tldr',[])),'## Management commentary',bullets(p.get('management_commentary',[])),'## Guidance / outlook',bullets(p.get('guidance',[])),'## Segment performance',bullets(p.get('segment_performance',[])),'## Key metrics',bullets(p.get('key_metrics',[])),'## Notable Q&A',bullets(p.get('notable_qa',[])),'## Risks / concerns',bullets(p.get('risks',[])),'','> Generated from transcript text. Empty sections mean the transcript did not provide supported information. Verify important figures against the original filing.']
    return '\n\n'.join(out)
