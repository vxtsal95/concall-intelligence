# Indian Concall Intelligence Pipeline

A modular take-home implementation for discovering NSE/BSE earnings-call transcript filings, downloading PDFs, extracting clean text, producing evidence-grounded summaries, and serving them through a dashboard and WebSocket.

## Architecture

1. **Watch & ingest** — polls NSE and BSE adapters every `POLL_INTERVAL_SECONDS`; filters transcript-like announcements; validates HTTPS and PDF magic bytes; deduplicates by normalized attachment URL.
2. **Extract** — PyMuPDF page-wise extraction, basic header/footer/page-number cleanup, and optional Tesseract OCR fallback for image-only PDFs.
3. **Summarize** — paragraph-aware overlapping chunks; map stage creates evidence notes; reduce stage returns the fixed JSON schema and Markdown. Temperature is zero and prompts prohibit unsupported claims.
4. **Serve** — FastAPI dashboard, JSON API, PDF route, and `/ws` live event feed.

## Setup

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows; use cp on macOS/Linux
```

Set `LLM_API_KEY` in `.env`. The API must be OpenAI-compatible. Configure `LLM_BASE_URL` and `LLM_MODEL` for another provider. **Without an API key, the watcher can discover, download and extract PDFs, but it will mark summarization as failed and will not fabricate sample summaries.**

Optional OCR: install the Tesseract executable and ensure it is on `PATH`.

## Run everything with one command

```bash
python run.py
```

Open http://localhost:8000. The watcher starts with the FastAPI app. API docs: http://localhost:8000/docs. WebSocket: `ws://localhost:8000/ws`.

## Output locations

- `data/raw/` — downloaded source PDFs.
- `data/processed/*.txt` — extracted transcript text.
- `data/processed/*.json` — structured summaries.
- `data/processed/*.md` — readable summaries.
- `data/concalls.db` — filing state and summary records.

## JSON schema

```json
{
  "company": "",
  "scrip_code": "",
  "nse_symbol": "",
  "quarter": "",
  "call_date": "",
  "source": "",
  "source_url": "",
  "tldr": [],
  "management_commentary": [],
  "guidance": [],
  "segment_performance": [{"segment": "", "notes": ""}],
  "key_metrics": [{"metric": "", "value": "", "context": ""}],
  "notable_qa": [{"question": "", "answer": "", "asked_by": ""}],
  "risks": []
}
```

The schema follows the assignment's example. The implementation allows empty arrays/strings where the transcript does not support a value. This is deliberate: missing information must not be guessed.

## Design decisions and trade-offs

- **Polling rather than exchange push notifications:** public exchange announcement endpoints are polled at a conservative configurable interval. This is near-real-time, not an exchange-provided push stream.
- **Exchange adapters are isolated:** NSE session bootstrap and BSE API handling are separate so endpoint changes do not affect extraction or serving. Exchange APIs can change, block automated requests, or alter response fields; check logs if discovery is empty.
- **Conservative filtering:** only titles explicitly containing transcript-related terms and a document URL are accepted. This reduces false positives but can miss filings with unusual wording. Expand `TRANSCRIPT_WORDS` after reviewing actual announcements.
- **Deduplication:** attachment URL hash prevents duplicate mirrored filings. A production system should also compare PDF hashes and company/date/title.
- **Chunking:** paragraph-aware chunks with overlap reduce context loss. Map-reduce costs more API calls but supports long 15–40+ page transcripts.
- **Faithfulness:** the model only sees transcript chunks and derived notes; temperature is zero; unsupported fields stay empty. Important investment decisions still require human verification.
- **Storage:** SQLite keeps the demo simple. PostgreSQL/object storage would be better for multi-worker production use.
- **WebSocket:** an in-process queue is sufficient for a single-process demo. Use Redis Pub/Sub or a broker for multiple workers/replicas.

## Known limitations

1. NSE/BSE endpoints are unofficially consumed and may change or rate-limit clients. The adapters log failures and continue polling.
2. The BSE response schema varies and may need field mapping updates against current live responses.
3. The first version filters by transcript keywords and is intentionally conservative; audio-only announcements are not transcribed.
4. OCR requires a separately installed Tesseract binary; OCR quality depends on scan quality.
5. PDF text reading order can still be imperfect for complex multi-column layouts.
6. The app uses one process and an in-memory WebSocket queue; not horizontally scalable.
7. LLM output must be reviewed. No automated model can guarantee zero hallucinations; source traceability and empty unsupported fields reduce risk.
8. No historical backfill or sentiment scoring is enabled by default.

## What I would do with more time

- Add robust exchange-specific schema tests and contract monitoring.
- Add PDF SHA-256 deduplication and retry queue with exponential backoff.
- Add XBRL metadata parsing and company/scrip master mapping.
- Store page numbers and verbatim evidence spans for every generated claim.
- Add audio transcription fallback for audio-only filings.
- Add Redis-backed event delivery, PostgreSQL, authentication, metrics and deployment containers.
- Build a review screen for correcting company metadata and approving summaries.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Sample outputs / honest submission note

The assignment requests raw transcripts and AI JSON/Markdown summaries for at least three companies. These must be generated from the actual downloaded source PDFs and a configured LLM key. This repository does not include invented financial figures or fabricated summaries. Run the watcher with a valid key; the first successfully discovered and processed transcripts will populate the output folders. For a deadline submission, also run a controlled one-time backfill against three confirmed transcript PDF URLs and include those source PDFs and generated outputs.

## Submission checklist

- [ ] Run `python run.py` and verify dashboard.
- [ ] Verify `/ws` receives a `new_summary` event after a new transcript is processed.
- [ ] Confirm at least three downloaded PDFs and matching `.txt`, `.json`, `.md` files.
- [ ] Inspect figures and Q&A against original PDFs.
- [ ] Push the repository to GitHub and invite `dy@saras.market` if private.
- [ ] Send repo URL and a 2–3 line walkthrough to `dy@saras.market`.
