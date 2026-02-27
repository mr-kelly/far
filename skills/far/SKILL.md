---
name: far
description: File-Augmented Retrieval — generate persistent .meta sidecar files for PDFs, images, spreadsheets, videos and more, making every binary file readable to AI coding agents.
allowed-tools: Read, Write, Edit, Bash, Glob
user-invocable: true
---

# 📄 /far - File-Augmented Retrieval

> **"Making Every File Readable to Coding Agents via Persistent .meta Sidecars"**

FAR is a file augmentation protocol that generates persistent `.meta` sidecar files for binary documents (PDF, DOCX, XLSX, PPTX, Images, etc.). This allows AI coding agents (like OpenClaw, Cursor, GitHub Copilot) to "read" non-text files directly from the file system without requiring external RAG infrastructure.

**Current Version:** 0.8.0
**Author:** Kelly Peilin Chan

---

## 🚀 The Problem: AI "Blindness"

AI agents operating in a repository can read code (`.py`, `.js`, `.md`), but they are blind to 30-40% of critical context stored in binary formats:
- **Product Specs**: `requirements.docx`
- **Design Mocks**: `architecture.png`
- **Financial Data**: `budget.xlsx`
- **Contracts**: `agreement.pdf`

When an agent encounters `budget.xlsx`, it sees opaque bytes. It cannot reason about the content.

## 💡 The Solution: Persistent Sidecars

FAR solves this by generating a human-readable and machine-readable `.meta` file next to every binary file.

**Example:**
```
project/
├── budget.xlsx         (Binary, opaque)
└── budget.xlsx.meta    (Markdown, readable)
```

The agent simply reads `budget.xlsx.meta` to understand the spreadsheet. No vector database, no API calls, no runtime overhead.

---

## ✨ Features

### 1. Broad Format Support
FAR extracts text and structure from a wide range of formats:
*   **📄 PDF** (`.pdf`): Full text extraction with layout preservation. **OCR fallback** for scanned PDFs. **Embedded image extraction** (pdfimages + OCR/Vision).
*   **📝 Word** (`.docx`, `.doc`): Text extraction.
*   **📊 Excel** (`.xlsx`): Sheet data converted to Markdown tables.
*   **📽️ PowerPoint** (`.pptx`): Slide text extraction.
*   **🖼️ Images** (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`): **OCR** (Tesseract) + **AI Vision** (GPT-4o) if configured.
*   **🎬 Media** (`.mp4`, `.mov`, `.mp3`, `.wav`, `.m4a`, `.flac`): Technical metadata (FFprobe) + **AI Transcription** (Whisper) if configured.
*   **📋 CSV** (`.csv`): Data rendered as Markdown tables (up to 100 rows).
*   **📓 Jupyter Notebook** (`.ipynb`): Markdown cells, code cells, and outputs.
*   **📚 EPUB** (`.epub`): Full text extracted from all chapters in spine order.
*   **🗜️ Archives** (`.zip`, `.jar`, `.whl`, `.apk`): File listing with sizes.
*   **📦 Tar** (`.tar`, `.tar.gz`, `.tgz`, `.bz2`, `.xz`): File listing with sizes.
*   **📧 Email** (`.eml`, `.msg`): Headers, body text, and attachment list.
*   **📝 RTF** (`.rtf`): Plain text extraction via control word stripping.
*   **💻 Code/Text** (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.md`, `.json`, ...): Direct content mirroring.

### 2. Intelligent Caching (Incremental Build)
FAR is designed for speed. It uses a **two-layer caching mechanism**:
1.  **Fast Check (mtime & size)**: If the file hasn't been modified, it skips processing instantly (0.003s).
2.  **Content Check (SHA256)**: If mtime changed, it calculates the file hash. If the content is identical, it updates the timestamp but skips re-extraction.

### 3. Directory Summaries (`.dir.meta`)
FAR generates a `.dir.meta` file in every directory, providing a high-level summary of all files within. This allows agents to "browse" a folder and understand its contents without reading every single file.

### 4. Git LFS Support
FAR automatically handles Git LFS pointer files. It will attempt to pull the real content before processing, ensuring you don't get empty metadata for LFS-tracked files.

---

## 🛠️ Usage

### Installation
The skill is pre-installed in the OpenClaw workspace:
```bash
~/.openclaw/workspace/.agents/skills/far/far_gen.py
```
A symlink is available as `far`:
```bash
far [directory_or_file]
```

### Commands

**Scan current directory (Recursive):**
```bash
far
```

**Scan specific directory:**
```bash
far ~/Documents/projects/files
```

**Process single file:**
```bash
far report.pdf
```

**Force regeneration (Ignore cache):**
```bash
far . --force
```

### Configuration (AI Features)
To enable AI features (Audio Transcription, Image Description), create a `.env` file in the skill directory or your home folder `~/.far.env`. 
Copy `.env.example` as a template:

```bash
OPENAI_API_KEY=sk-your-key-here
# Optional
OPENAI_BASE_URL=https://api.openai.com/v1
```

If API keys are missing, FAR gracefully falls back to local tools (Tesseract, FFprobe).

### Configuration (Ignore)
Create a `.farignore` file in your project root to exclude files or directories from scanning.
```gitignore
# .farignore
node_modules
.git
secrets/
*.tmp
```

---

## 🏗️ Protocol Specification (v1)

Each `.meta` file follows a strict format with a YAML frontmatter header and Markdown body.

```markdown
--far_version: 1
source:
  sha256: 5a1cc2b8d...
  mime: application/pdf
  size: 129509
  mtime: 1708845210.5
extract:
  pipeline: far_gen_v5
  extracted_at: 2026-02-25T16:35:18Z
---
# filename.pdf

[Extracted Content Here...]
```

---

## 🤝 Contributing

This skill is part of the **OpenClaw Agent Ecosystem**.
Location: `~/.openclaw/workspace/.agents/skills/far/`

**Roadmap:**
- [x] PDF/Word/Excel Support
- [x] PowerPoint Support
- [x] Incremental Caching (mtime)
- [x] Directory Summaries
- [x] OCR for Images/Scanned PDFs (Tesseract)
- [x] Media Metadata (FFprobe)
- [x] Audio/Video Transcription (Whisper)
- [x] AI Vision for Images (GPT-4o)
- [ ] Rust Implementation for CI/CD speed
