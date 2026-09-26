# UPSC Adaptive Test — Data Pipeline

Data ingestion & extraction for an adaptive UPSC Prelims/Mains practice test.

## Layout

```
config/
  sources.yaml            source registry + confidence (verified/unverified/excluded)
  syllabus_taxonomy.yaml  topic tree used to tag every question/content chunk
  rss_feeds.yaml          current-affairs RSS feed list
data/
  raw/                    downloaded source files (gitignored, PDFs not committed)
  processed/              extracted structured JSON/JSONL
scripts/
  ingest/fetch_rss.py     pulls current-affairs RSS feeds -> jsonl
  extract/pdf_to_text.py  PDF -> plain text
  extract/parse_questions.py  text -> structured MCQ JSON, tagged by topic
  extract/merge_answer_key.py merge a bare answer key into parsed questions
```

## Confidence model

Every record carries a `confidence` field:
- `verified` — official govt (UPSC, PIB, PRS) or NCERT source. Ground truth.
- `unverified` — third-party compilation. Used only as a bonus practice
  pool, flagged in the UI, never treated as authoritative.

See `config/sources.yaml` for the full registry, including sources
deliberately excluded (SSC CGL paper — wrong exam; coaching material —
copyright + reliability).

## Pipeline (current state)

1. `pdf_to_text.py` — extract raw text from a PDF.
2. `parse_questions.py` — split text into numbered questions + options,
   tag each with a syllabus topic id from `syllabus_taxonomy.yaml`.
3. `merge_answer_key.py` — attach answers once a key is confirmed to
   match a given question set.
4. `fetch_rss.py` — daily pull of PIB/PRS feeds into
   `data/processed/current_affairs/feed_items.jsonl`.

## Next steps

- Download official UPSC syllabus + Prelims/Mains papers (2013+) from
  upsc.gov.in into `data/raw/upsc_official/`.
- Download NCERT PDFs (6-12, relevant subjects) into `data/raw/ncert/`.
- Cross-check `UPSC_Questions.pdf` (unverified) against official papers
  to promote confirmed matches to `verified`.
- Wire `fetch_rss.py` into a scheduled job (cron / GitHub Actions).
