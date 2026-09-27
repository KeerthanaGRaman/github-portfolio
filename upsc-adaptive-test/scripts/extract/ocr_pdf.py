"""OCR fallback for PDFs with no usable text layer (scanned pages,
photographed answer sheets, old exam papers photocopied into a PDF).

Normal pipeline order: try pdftotext first (extract_pdf_to_text via
pdf_to_text.py). Only reach for this script once that comes back empty
or near-empty for a page - OCR is slower and noisier than a real text
layer, never a first choice.

How it works:
    1. Render each PDF page to a PNG at 300 DPI (pdftoppm) - OCR
       accuracy is very sensitive to resolution; 300 DPI is the
       standard floor for clean scans, higher for small/dense text.
    2. Run Tesseract on each page image.
    3. Concatenate page results into one text file, same "--- page N
       ---" marker convention pdf_to_text.py uses, so downstream
       parsing (parse_questions.py etc.) doesn't need to care whether
       a document came from a real text layer or from OCR.

Usage:
    python ocr_pdf.py <input.pdf> <output.txt> [--dpi 300] [--lang eng]

Quality note: this is classic OCR (Tesseract), which struggles with
rotated pages, dense tables, and poor scans. A vision-capable model
reading the page image directly often does better on messy layouts -
worth trying by hand on anything Tesseract garbles badly.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def render_pages(pdf_path: Path, tmp_dir: Path, dpi: int) -> list[Path]:
    prefix = tmp_dir / "page"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        capture_output=True, check=True,
    )
    return sorted(tmp_dir.glob("page-*.png"))


def ocr_image(image_path: Path, lang: str) -> str:
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", lang],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"tesseract failed on {image_path}: {result.stderr}")
    return result.stdout


def ocr_pdf(pdf_path: str, out_path: str, dpi: int = 300, lang: str = "eng") -> None:
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        pages = render_pages(pdf_path, tmp_dir, dpi)
        if not pages:
            raise RuntimeError(f"pdftoppm produced no pages for {pdf_path}")

        chunks = []
        for i, page_img in enumerate(pages, start=1):
            text = ocr_image(page_img, lang)
            chunks.append(f"--- page {i} ---\n{text}")
            print(f"  page {i}/{len(pages)}: {len(text)} chars", file=sys.stderr)

    out_path.write_text("\n\n".join(chunks), encoding="utf-8")
    print(f"OCR'd {len(pages)} pages -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("output_txt")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default="eng", help="Tesseract language code, e.g. 'eng', 'hin', 'eng+hin'")
    args = ap.parse_args()

    ocr_pdf(args.pdf_path, args.output_txt, args.dpi, args.lang)


if __name__ == "__main__":
    main()
