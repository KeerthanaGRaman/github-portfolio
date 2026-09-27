# UPSC Adaptive Test — Data Pipeline

Data ingestion & extraction for an adaptive UPSC Prelims/Mains practice test.

## Layout

```
config/
  sources.yaml            source registry + confidence (verified/unverified/excluded)
  syllabus_taxonomy.yaml  topic tree used to tag every question/content chunk
  ncert_books.yaml        NCERT book-code registry (classes 6-12)
  rss_feeds.yaml          current-affairs RSS feed list
data/
  raw/                    downloaded/intermediate files (gitignored - never committed)
  processed/              compiled, tagged corpora (committed)
    syllabus/             NCERT corpus (ncert_corpus.jsonl) + fetch manifest
    questions/            parsed MCQ banks
    current_affairs/      RSS feed items (feed_items.jsonl)
scripts/
  ingest/fetch_ncert.py   downloads + extracts NCERT chapter PDFs -> text
  ingest/fetch_rss.py     pulls current-affairs RSS feeds -> jsonl
  ingest/scrape_prs.py    scrapes PRS's Bills Track listing (no RSS exists) -> jsonl
  extract/pdf_to_text.py  PDF -> plain text (pdftotext)
  extract/ocr_pdf.py      OCR fallback for scanned/image-only PDFs (pdftoppm + tesseract)
  extract/parse_questions.py    text -> structured MCQ JSON, tagged by topic
  extract/merge_answer_key.py   merge a bare answer key into parsed questions
  extract/build_ncert_corpus.py compile fetched NCERT chapters -> committed corpus
  extract/extract_images.py     pull real content images out of a PDF, filtering boilerplate
```

## Confidence model

Every record carries a `confidence` field:
- `verified` — official govt (UPSC, PIB) or NCERT source. Ground truth.
- `unverified` — third-party compilation. Used only as a bonus practice
  pool, flagged in the UI, never treated as authoritative.

See `config/sources.yaml` for the full registry, including sources
deliberately excluded (SSC CGL paper — wrong exam; coaching material —
copyright + reliability).

## Language scope

- **NCERT**: English medium only.
- **Current affairs (PIB)**: both English and Hindi are kept — the app
  uses both. PIB's feed mixes languages per release regardless of any
  `Lang` param, so `fetch_rss.py` tags each item's detected script
  (`hindi`/`english`) rather than trusting the feed to separate them.

## Pipeline (current state)

1. `fetch_ncert.py` — downloads each NCERT chapter PDF, extracts text
   via `pdftotext`, discards the PDF (chapters run 5-15MB with images).
2. `build_ncert_corpus.py` — compiles fetched chapters + manifest into
   the committed `data/processed/syllabus/ncert_corpus.jsonl`.
3. `pdf_to_text.py` / `parse_questions.py` / `merge_answer_key.py` —
   extract and tag MCQs from uploaded question-paper PDFs.
4. `fetch_rss.py` — pull of PIB current-affairs feed into
   `data/processed/current_affairs/feed_items.jsonl` (dedup by link,
   retries on PIB's flaky TLS resets).
5. `scrape_prs.py` — scrapes PRS's public `/billtrack` listing (no RSS
   feed exists there) into `data/processed/current_affairs/prs_bills.jsonl`
   (deduped by link, re-run updates a bill's status in place). Respects
   `robots.txt`'s `Crawl-delay: 10`; stores only title/status/link, not
   PRS's own bill-summary text.
6. `ocr_pdf.py` — fallback for when `pdf_to_text.py` comes back empty
   (a scanned/photographed page has no real text layer). Renders each
   page to a PNG (`pdftoppm`, 300 DPI) and runs Tesseract on it, output
   in the same `--- page N ---` format `pdf_to_text.py` uses so
   downstream parsing doesn't care which one produced the text.
   Validated against a synthetic image-only PDF (real text rendered to
   an image, then saved with no text layer): Tesseract recovered the
   content but misread `(b)` as `(6)`/`(6b)` twice - classic OCR
   character-shape confusion. Re-read the same image with a
   vision-capable model instead: 100% correct, no `(b)`/`(6)` errors -
   vision models use surrounding context ("this is an (a)(b)(c)(d)
   list") rather than matching character shapes in isolation. Tesseract
   stays the automated default (cheap, scriptable, no model call per
   page); a vision-model read is worth doing by hand on anything
   Tesseract garbles, especially in the "unverified" question-answer
   space where a misread letter silently flips a correct answer choice.

## Known blockers

- **upsc.gov.in** is unreachable from this environment — the server
  resets the TLS connection for every request (a server-side block on
  this IP range, not a local network-policy issue). Official UPSC
  syllabus/papers/answer-keys still need to come in via manual upload.

## Next steps

- Get official UPSC syllabus + Prelims/Mains papers (2013+) via manual
  upload into `data/raw/upsc_official/`, then run them through the
  question-parsing pipeline.
- Cross-check `UPSC_Questions.pdf` (answers now merged in, still
  `unverified`) against official papers to promote confirmed matches
  to `verified`.
- Wire `fetch_rss.py` and `scrape_prs.py` (and eventually
  `fetch_ncert.py`, one-off) into a scheduled job (cron / GitHub Actions).
