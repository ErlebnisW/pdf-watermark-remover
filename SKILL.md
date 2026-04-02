---
name: pdf-watermark-remover
description: Remove text watermarks from PDF files. Use when the user asks to "remove watermark", "delete watermark", "去水印", "去掉水印", "删除水印", or mentions cleaning up diagonal/rotated text overlays on PDF documents. Handles the common pattern of repeated diagonal text watermarks (e.g., names, timestamps, "CONFIDENTIAL") rendered at 45-degree rotation in PDF content streams.
---

# PDF Watermark Remover

Remove diagonal text watermarks from PDFs using PyMuPDF. Requires `pymupdf` (`pip install pymupdf`).

## Workflow

1. Ensure pymupdf is installed: `pip install pymupdf`
2. Run the removal script:

```bash
# Single PDF
python scripts/remove_watermark.py "<input.pdf>" ["<output.pdf>"]

# Folder (creates <folder>_no_watermark/ with all files)
python scripts/remove_watermark.py "<input_folder>"
```

Single PDF output defaults to `<input>_no_watermark.pdf` if omitted.
Folder mode creates `<folder>_no_watermark/` containing processed PDFs (watermarks removed) and non-PDF files copied as-is.

3. Verify result by reading the output PDF visually.

## How It Works

Most text watermarks are rendered as rotated text in PDF content streams using a 45-degree transformation matrix (`0.70711 0.70711 -0.70711 0.70711`). The script scans each page's content streams for this rotation signature and removes matching streams while preserving the document's graphics state balance (`q`/`Q` pairs).

## Limitations

- Targets 45-degree rotated text watermarks only (the most common type)
- Does not remove image-based watermarks (rasterized overlays)
- Does not remove watermarks embedded as part of the main content stream (rare)
- If the document has legitimate 45-degree rotated text, it may be removed too

## Manual Approach

When the script doesn't cover an edge case, use PyMuPDF directly:

```python
import fitz

doc = fitz.open("input.pdf")
for page_num in range(doc.page_count):
    page = doc[page_num]
    for c_xref in page.get_contents():
        stream = doc.xref_stream(c_xref)
        if stream is None:
            continue
        text = stream.decode("latin-1", errors="replace")
        # Customize detection: match on font name, text content, or rotation
        if "YOUR_WATERMARK_PATTERN" in text:
            doc.update_stream(c_xref, b" Q\n")
doc.save("output.pdf", garbage=4, deflate=True)
doc.close()
```

Common detection patterns:
- **By rotation**: `"0.70711 0.70711 -0.70711 0.70711"` (45-degree)
- **By font name**: `"/Xi1 15 Tf"` (watermark-specific font)
- **By transparency**: `"/Xi0 gs"` (graphics state with alpha)
