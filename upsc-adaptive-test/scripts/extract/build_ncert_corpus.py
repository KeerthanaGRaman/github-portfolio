"""Compile the raw NCERT chapter text files + fetch manifest into a
single committed corpus file: one JSON record per chapter, with text
inlined, ready for downstream chunking/embedding.

Two cleanup passes are applied to the raw pdftotext output:

1. Strip print-production artifact lines (e.g. "chapter0_310125.indd 1
   ... 03-02-2025 04:56:20") that leak into the text layer of every
   page - cosmetic noise, safe to remove outright.

2. Flag (never silently reorder) chapters likely to contain a
   scrambled reading order. pdftotext -layout preserves the *visual*
   column position of text, which works perfectly for normal
   paragraphs but breaks for boxed callouts (e.g. this series' "Let's
   Explore" question grids, or a chapter-opening theme diagram) - their
   side-by-side layout gets flattened into jumbled fragments. There is
   no reliable text-only fix for this (it would need rendering the page
   as an image and reading it with OCR/vision); we mark the chapter
   with `layout_warning: true` instead of pretending it's clean.

Reads:  data/processed/syllabus/ncert_manifest.jsonl (written by fetch_ncert.py)
        data/raw/ncert/<code>/<code><NN>.txt          (chapter text)
Writes: data/processed/syllabus/ncert_corpus.jsonl

Usage:
    python build_ncert_corpus.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
MANIFEST = ROOT / "data" / "processed" / "syllabus" / "ncert_manifest.jsonl"
OUT = ROOT / "data" / "processed" / "syllabus" / "ncert_corpus.jsonl"

# Matches a whole line that is a print-production artifact, e.g.:
#   "chapter0_310125.indd 1  ...  03-02-2025 04:56:20"
#   "chapter1_310125.indd 8  ...  09-Apr-26 4:15:37 PM"
PRODUCTION_ARTIFACT_RE = re.compile(r"^\S+\.indd\s+\d+.*$", re.MULTILINE)

# Heuristic for "this chapter probably has a scrambled box/diagram
# somewhere": a cluster of short, question-like fragments (a hallmark
# of these side-by-side callout boxes) close together. Not proof of
# scrambling, just a signal worth a human glance.
LAYOUT_WARNING_MARKERS = ("LET'S EXPLORE", "LET US EXPLORE", "THEME A", "THEME B")


def clean_text(text: str) -> str:
    text = PRODUCTION_ARTIFACT_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank-line runs left behind
    return text.strip()


def looks_layout_scrambled(text: str) -> bool:
    return any(marker in text.upper() for marker in LAYOUT_WARNING_MARKERS)


def main():
    records = []
    flagged = 0
    with MANIFEST.open(encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            text_path = ROOT / entry["text_path"]
            if not text_path.exists():
                print(f"WARN: missing text file {text_path}, skipping")
                continue
            raw_text = text_path.read_text(encoding="utf-8", errors="replace")
            text = clean_text(raw_text)
            layout_warning = looks_layout_scrambled(text)
            flagged += layout_warning
            records.append({
                "source_id": entry["source_id"],
                "book_code": entry["book_code"],
                "book_title": entry["book_title"],
                "class": entry["class"],
                "chapter": entry["chapter"],
                "topics": entry["topics"],
                "confidence": entry["confidence"],
                "char_count": len(text),
                "layout_warning": layout_warning,
                "text": text,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_chars = sum(r["char_count"] for r in records)
    print(f"Compiled {len(records)} chapters ({total_chars:,} chars) -> {OUT}")
    print(f"{flagged} / {len(records)} chapters flagged with layout_warning=true (possible box/diagram scrambling)")


if __name__ == "__main__":
    main()
