"""Download NCERT textbook chapters (per config/ncert_books.yaml) and
extract text immediately, discarding the PDF afterward to save disk
(chapter PDFs run 5-15MB each due to embedded images).

For each book code <c>, chapters are fetched from:
    https://ncert.nic.in/textbook/pdf/<c><NN>.pdf   (NN = 01, 02, ...)
stopping early on a 404/empty response, so `chapters` in the config
only needs to be an upper bound.

Output: one text file per chapter at
    data/raw/ncert/<code>/<code><NN>.txt
plus data/processed/syllabus/ncert_manifest.jsonl recording what was
fetched, its topic tags and confidence (always "verified" - NCERT is
an official govt source).

Usage:
    python fetch_ncert.py [--config ../../config/ncert_books.yaml] [--only keec1,kegy1]
"""
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE_URL = "https://ncert.nic.in/textbook/pdf"
ROOT = Path(__file__).parent.parent.parent


def download_pdf(url: str, dest: Path) -> bool:
    """Return True if a real PDF was downloaded (non-empty, status 200)."""
    result = subprocess.run(
        ["curl", "-sSL", "--max-time", "60", "-w", "%{http_code}",
         "-o", str(dest), url],
        capture_output=True, text=True,
    )
    status = result.stdout.strip()
    if status != "200" or not dest.exists() or dest.stat().st_size < 1000:
        dest.unlink(missing_ok=True)
        return False
    return True


def pdf_to_text(pdf_path: Path, txt_path: Path) -> None:
    subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)],
                    capture_output=True, text=True, check=True)


def fetch_book(book: dict, raw_dir: Path) -> list[dict]:
    code = book["code"]
    out_dir = raw_dir / code
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for n in range(1, book["chapters"] + 1):
            chapter_id = f"{n:02d}"
            url = f"{BASE_URL}/{code}{chapter_id}.pdf"
            tmp_pdf = tmp / f"{code}{chapter_id}.pdf"

            ok = download_pdf(url, tmp_pdf)
            if not ok:
                print(f"  {code}{chapter_id}: not found, stopping book (got {n - 1} chapters)")
                break

            txt_path = out_dir / f"{code}{chapter_id}.txt"
            pdf_to_text(tmp_pdf, txt_path)
            tmp_pdf.unlink(missing_ok=True)  # discard PDF, keep only text

            size = txt_path.stat().st_size
            print(f"  {code}{chapter_id}: OK ({size} bytes text)")
            manifest_entries.append({
                "source_id": "ncert",
                "book_code": code,
                "book_title": book["title"],
                "class": book["class"],
                "chapter": n,
                "topics": book["topics"],
                "text_path": str(txt_path.relative_to(ROOT)),
                "confidence": "verified",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    return manifest_entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config" / "ncert_books.yaml"))
    ap.add_argument("--only", help="Comma-separated book codes to restrict to")
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw" / "ncert"))
    ap.add_argument("--manifest", default=str(ROOT / "data" / "processed" / "syllabus" / "ncert_manifest.jsonl"))
    args = ap.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    books = config["books"]
    if args.only:
        wanted = set(args.only.split(","))
        books = [b for b in books if b["code"] in wanted]

    raw_dir = Path(args.raw_dir)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    all_entries = []
    for book in books:
        print(f"=== {book['code']}: {book['title']} ===")
        try:
            entries = fetch_book(book, raw_dir)
            all_entries.extend(entries)
        except Exception as e:
            print(f"  ERROR fetching {book['code']}: {e}", file=sys.stderr)

    with manifest_path.open("a", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\nDone. {len(all_entries)} chapters fetched -> {manifest_path}")


if __name__ == "__main__":
    main()
