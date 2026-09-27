"""Extract "real" images (diagrams, maps, charts) from a PDF, filtering
out repeated boilerplate (logos, letterheads, watermarks).

Two independent boilerplate signals, either one is enough to exclude:
  1. Same embedded PDF object reused across many pages (a logo embedded
     once and referenced repeatedly) - the strongest signal, read
     straight from `pdfimages -list`.
  2. Same rendered content by hash, even if re-embedded as separate
     objects per page (some PDF generators do this instead of reusing
     one object) - covered by hashing every extracted image and
     dropping hashes that recur past `--max-repeats`.

Usage:
    python extract_images.py <input.pdf> <output_dir> [--max-repeats 2]

Output: <output_dir>/pXXX_imgN.png per kept image, plus
<output_dir>/manifest.json listing {page, path, width, height} for
each one (this is what a question-parsing step joins against to
attach images to nearby questions by page number).
"""
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

LIST_RE = re.compile(
    r"^\s*(?P<page>\d+)\s+(?P<num>\d+)\s+\S+\s+(?P<width>\d+)\s+(?P<height>\d+).*?"
    r"\s(?P<object_id>\d+)\s+\d+\s+\d+\s+\S+\s+\S+\s*$"
)


def list_images(pdf_path: Path) -> list[dict]:
    result = subprocess.run(["pdfimages", "-list", str(pdf_path)],
                             capture_output=True, text=True, check=True)
    entries = []
    for line in result.stdout.splitlines()[2:]:  # skip the two header lines
        m = LIST_RE.match(line)
        if m:
            entries.append({k: int(v) for k, v in m.groupdict().items()})
    return entries


def object_id_repeat_counts(entries: list[dict]) -> Counter:
    return Counter(e["object_id"] for e in entries)


def extract_all(pdf_path: Path, tmp_dir: Path) -> None:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdfimages", "-png", str(pdf_path), str(tmp_dir / "img")],
                    capture_output=True, check=True)


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("output_dir")
    ap.add_argument("--max-repeats", type=int, default=2,
                     help="An object ID or identical image appearing on more "
                          "than this many pages is treated as boilerplate")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    out_dir = Path(args.output_dir)
    tmp_dir = out_dir / "_tmp_extracted"

    entries = list_images(pdf_path)
    repeat_counts = object_id_repeat_counts(entries)
    boilerplate_object_ids = {oid for oid, count in repeat_counts.items()
                               if count > args.max_repeats}

    extract_all(pdf_path, tmp_dir)
    extracted_files = sorted(tmp_dir.glob("img-*.png"))

    if len(extracted_files) != len(entries):
        print(f"WARN: pdfimages -list found {len(entries)} images but "
              f"-png extracted {len(extracted_files)}; page/file order may "
              f"not line up 1:1 for every entry (multi-image pages can "
              f"differ in ordering) - verify the manifest.")

    out_dir.mkdir(parents=True, exist_ok=True)
    seen_hashes: dict[str, int] = {}
    hash_counts = Counter()
    # First pass: count how many times each rendered image repeats,
    # independent of object ID (covers generators that re-embed instead
    # of reusing one object).
    for f in extracted_files:
        hash_counts[file_hash(f)] += 1

    manifest = []
    kept = 0
    for entry, f in zip(entries, extracted_files):
        h = file_hash(f)
        is_boilerplate = (
            entry["object_id"] in boilerplate_object_ids
            or hash_counts[h] > args.max_repeats
        )
        if is_boilerplate:
            continue

        dest_name = f"p{entry['page']:03d}_img{entry['num']}.png"
        dest_path = out_dir / dest_name
        f.rename(dest_path)
        manifest.append({
            "page": entry["page"],
            "path": str(dest_path),
            "width": entry["width"],
            "height": entry["height"],
        })
        kept += 1

    for f in extracted_files:
        f.unlink(missing_ok=True)
    tmp_dir.rmdir()

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(entries)} images found, {kept} kept as real content, "
          f"{len(entries) - kept} filtered as boilerplate -> {out_dir}")


if __name__ == "__main__":
    main()
