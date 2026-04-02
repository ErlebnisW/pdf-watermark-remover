# PDF 水印去除 (PDF Watermark Remover)

Remove diagonal text watermarks from PDF files. Supports both single files and batch folder processing.

## Features

- **Two watermark types**: separate-stream watermarks and inline embedded watermarks
- **Batch processing**: process entire folders, preserving directory structure
- **macOS App**: self-contained `.app` with drag-and-drop UI (no Python needed)
- **CLI script**: lightweight command-line tool for automation
- **Claude Code Skill**: integrates as a skill for Claude Code users

## macOS App

Download `PDF水印去除.app` from [Releases](../../releases) — double-click to use, no installation required.

- Drag PDF files or folders onto the app icon
- Or open the app and use the in-window drop zone
- Progress bar with real-time status
- Output path shown on completion

### Build from source

```bash
pip install pymupdf pyinstaller tkinterdnd2
pyinstaller --onedir --windowed --name "PDF水印去除" \
  --icon AppIcon.icns --noconfirm \
  --hidden-import fitz --hidden-import pymupdf \
  --hidden-import tkinterdnd2 --collect-all tkinterdnd2 \
  --exclude-module numpy --exclude-module pandas \
  --exclude-module scipy --exclude-module matplotlib \
  app.py
```

## CLI Usage

```bash
pip install pymupdf

# Single PDF
python scripts/remove_watermark.py input.pdf [output.pdf]

# Folder (creates <folder>_no_watermark/)
python scripts/remove_watermark.py /path/to/folder
```

## How It Works

Text watermarks in PDFs are rendered as rotated text in content streams. This tool detects two common patterns:

1. **Separate stream**: watermark in its own content stream using a 45-degree unit rotation matrix (`0.70711 0.70711 -0.70711 0.70711`)
2. **Inline**: watermark blocks embedded in the main content stream with a scaled rotation matrix (`a a -a a` where `a = fontSize * 0.70711`)

Matched watermark content is surgically removed while preserving all other document content.

## License

MIT
