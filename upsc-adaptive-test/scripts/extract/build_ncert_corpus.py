"""Compile the raw NCERT chapter text files + fetch manifest into a
single committed corpus file: one JSON record per chapter, with text
inlined, ready for downstream chunking/embedding.

Reads:  data/processed/syllabus/ncert_manifest.jsonl (written by fetch_ncert.py)
        data/raw/ncert/<code>/<code><NN>.txt          (chapter text)
Writes: data/processed/syllabus/ncert_corpus.jsonl

Usage:
    python build_ncert_corpus.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
MANIFEST = ROOT / "data" / "processed" / "syllabus" / "ncert_manifest.jsonl"
OUT = ROOT / "data" / "processed" / "syllabus" / "ncert_corpus.jsonl"


def main():
    records = []
    with MANIFEST.open(encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            text_path = ROOT / entry["text_path"]
            if not text_path.exists():
                print(f"WARN: missing text file {text_path}, skipping")
                continue
            text = text_path.read_text(encoding="utf-8", errors="replace").strip()
            records.append({
                "source_id": entry["source_id"],
                "book_code": entry["book_code"],
                "book_title": entry["book_title"],
                "class": entry["class"],
                "chapter": entry["chapter"],
                "topics": entry["topics"],
                "confidence": entry["confidence"],
                "char_count": len(text),
                "text": text,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_chars = sum(r["char_count"] for r in records)
    print(f"Compiled {len(records)} chapters ({total_chars:,} chars) -> {OUT}")


if __name__ == "__main__":
    main()
