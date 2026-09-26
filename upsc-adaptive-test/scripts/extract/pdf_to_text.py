"""Convert a PDF into plain text, page by page.

Uses the `pdftotext` binary (poppler-utils) rather than a Python PDF
library, since it has no fragile native-extension dependencies.

Usage:
    python pdf_to_text.py <input.pdf> <output.txt>
"""
import subprocess
import sys
from pathlib import Path


def pdf_to_text(pdf_path: str, out_path: str) -> None:
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    pdf_to_text(sys.argv[1], sys.argv[2])
