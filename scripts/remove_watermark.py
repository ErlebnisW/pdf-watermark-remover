#!/usr/bin/env python3
"""Remove text watermarks from PDF files using PyMuPDF.

Detects watermarks by identifying rotated text patterns (45-degree diagonal)
in PDF content streams, which is the most common watermark rendering technique.

Supports two watermark types:
  1. Separate stream: watermark in its own content stream with unit rotation matrix
  2. Inline: watermark blocks embedded in main content with scaled rotation matrix

Usage:
    python remove_watermark.py <input.pdf> [output.pdf]
    python remove_watermark.py <input_folder>

For a single PDF, output defaults to <input>_no_watermark.pdf.
For a folder, creates <folder>_no_watermark/ with processed PDFs and copied non-PDFs.
"""

import re
import shutil
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


# Pattern 1: separate stream with unit 45-degree rotation matrix
ROTATION_PATTERN = "0.70711 0.70711 -0.70711 0.70711"

# Pattern 2: inline watermark blocks with scaled 45-degree rotation (a a -a a Tm)
INLINE_WM_RE = re.compile(
    r'q\s+'
    r'[\d.]+\s+0\s+0\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*'
    r'cm\s+BT\s+'
    r'([\d.]+)\s+\1\s+-\1\s+\1'
    r'.*?'
    r'TJ\s+ET\s*Q',
    re.DOTALL
)


def _check_stream(text: str) -> str:
    """Return watermark type: 'separate', 'inline', or 'none'."""
    if ROTATION_PATTERN in text:
        return "separate"
    if INLINE_WM_RE.search(text):
        return "inline"
    return "none"


def has_watermark(pdf_path: str) -> bool:
    """Check if a PDF contains 45-degree rotated text watermarks."""
    doc = fitz.open(pdf_path)
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for c_xref in page.get_contents():
            stream = doc.xref_stream(c_xref)
            if stream is None:
                continue
            if _check_stream(stream.decode("latin-1", errors="replace")) != "none":
                doc.close()
                return True
    doc.close()
    return False


def remove_watermark(input_path: str, output_path: str | None = None) -> str:
    """Remove text watermarks from a PDF file.

    Args:
        input_path: Path to the input PDF.
        output_path: Path for the output PDF. Auto-generated if None.

    Returns:
        Path to the saved output file.
    """
    input_file = Path(input_path)
    if output_path is None:
        output_path = str(input_file.with_stem(input_file.stem + "_no_watermark"))

    doc = fitz.open(str(input_file))
    removed_count = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for c_xref in page.get_contents():
            stream = doc.xref_stream(c_xref)
            if stream is None:
                continue
            text = stream.decode("latin-1", errors="replace")
            wm_type = _check_stream(text)

            if wm_type == "separate":
                doc.update_stream(c_xref, b" Q\n")
                removed_count += 1
            elif wm_type == "inline":
                cleaned = INLINE_WM_RE.sub('', text)
                doc.update_stream(c_xref, cleaned.encode("latin-1"))
                removed_count += 1

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    print(f"  Removed watermarks from {removed_count} page(s): {Path(output_path).name}")
    return output_path


def process_folder(folder_path: str) -> str:
    """Process a folder: remove watermarks from PDFs, copy other files."""
    src = Path(folder_path)
    dst = src.parent / (src.name + "_no_watermark")
    dst.mkdir(exist_ok=True)

    pdf_count = 0
    watermark_count = 0
    copy_count = 0

    for item in sorted(src.rglob("*")):
        if item.is_dir():
            continue

        rel = item.relative_to(src)
        out_file = dst / rel
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if item.suffix.lower() == ".pdf":
            pdf_count += 1
            if has_watermark(str(item)):
                watermark_count += 1
                remove_watermark(str(item), str(out_file))
            else:
                shutil.copy2(item, out_file)
                print(f"  No watermark, copied: {rel}")
        else:
            shutil.copy2(item, out_file)
            copy_count += 1
            print(f"  Copied: {rel}")

    print(f"\nDone! {watermark_count}/{pdf_count} PDFs had watermarks removed, "
          f"{copy_count} non-PDF files copied.")
    print(f"Output: {dst}")
    return str(dst)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.pdf|folder> [output.pdf]")
        sys.exit(1)

    in_path = Path(sys.argv[1])

    if in_path.is_dir():
        process_folder(str(in_path))
    else:
        out_path = sys.argv[2] if len(sys.argv) > 2 else None
        remove_watermark(str(in_path), out_path)
