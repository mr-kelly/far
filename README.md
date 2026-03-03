<div align="center">

# 📄 FAR - File-Augmented Retrieval

**Making Every File Readable to AI Coding Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/mr-kelly/far)

[📖 Read the Paper](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf) • [🚀 Quick Start](#-quick-start) • [✨ Features](#-features)

</div>

---

> *"RAG performs retrieval at query time. FAR performs augmentation at file time."*
> — [FAR Paper, Kelly Peilin Chan, 2026](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf)

---

## 🚀 Quick Start

### Install

**In Claude Code:**
```
/plugin marketplace add mr-kelly/far
/plugin install far
```

**Via npx (other AI agents):**
```bash
npx skills add mr-kelly/far
```

**Manual:**
```bash
git clone https://github.com/mr-kelly/far.git
```

### Run

```bash
# Scan current directory (recursive)
far

# Scan specific directory
far ~/Documents/projects

# Process single file
far report.pdf

# Force regeneration (ignore cache)
far . --force
```

### One Rule for Your Agent

Add to `AGENTS.md` or system prompt — that's all:

```
When you encounter a binary file you cannot read
(.png, .pdf, .xlsx, .mp4), check for a .meta file
beside it. The .meta contains extracted content as
Markdown. For directory overviews, read .dir.meta.
```

### Configuration (AI Features)

```bash
cp skills/far/.env.example skills/far/.env
# Add OPENAI_API_KEY to enable vision + transcription
```

Without API keys, FAR falls back to local tools (Tesseract, FFprobe).

---

## 🎯 The Problem

AI coding agents (Claude Code, Codex, GitHub Copilot) can read code — but they're **blind to 30–40% of critical context** stored in binary formats:

| File | Agent sees |
|------|-----------|
| `budget.xlsx` | Opaque bytes |
| `architecture.png` | Nothing |
| `requirements.pdf` | Nothing |
| `standup.mp4` | Nothing |

> *"An AI agent operating without access to these files is like a developer who can read code but is forbidden from looking at the design docs, the architecture diagrams, or the product requirements."*

## 💡 The Solution

FAR generates a persistent `.meta` sidecar next to every binary file:

```
project/
├── budget.xlsx           ← Binary (opaque to AI)
├── budget.xlsx.meta      ← Markdown table (readable by AI)
├── architecture.png      ← Binary
├── architecture.png.meta ← Caption + OCR text
└── standup.mp4.meta      ← Full transcript + topics
```

**No vector database. No embedding service. No runtime pipeline.**

---

## ✨ Features

### 📦 Supported Formats

| Format | Extensions | Extractor | Output |
|--------|-----------|-----------|--------|
| 📄 PDF | `.pdf` | pdfminer + tabula | Full text, tables as Markdown |
| 📝 Word | `.docx`, `.doc` | python-docx / antiword | Full text |
| 📊 Excel | `.xlsx` | openpyxl | Sheets as Markdown tables |
| 📽️ PowerPoint | `.pptx` | python-pptx | Slide text |
| 🖼️ Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp` | Tesseract OCR + GPT-4V | Caption + OCR text |
| 🎬 Video | `.mp4`, `.mov`, `.avi`, `.mkv` | ffmpeg + Whisper | Metadata + transcript |
| 🎵 Audio | `.mp3`, `.wav`, `.m4a`, `.flac` | Whisper | Transcript |
| 📋 CSV | `.csv` | Built-in | Markdown table (up to 100 rows) |
| 📓 Jupyter | `.ipynb` | Built-in | Markdown + code cells + outputs |
| 📚 EPUB | `.epub` | Built-in | Full text from all chapters |
| 🗜️ Archive | `.zip`, `.jar`, `.whl`, `.apk` | Built-in | File listing with sizes |
| 📦 Tar | `.tar`, `.tar.gz`, `.tgz`, `.bz2`, `.xz` | Built-in | File listing with sizes |
| 📧 Email | `.eml`, `.msg` | Built-in | Headers + body + attachment list |
| 📝 RTF | `.rtf` | Built-in | Plain text extraction |
| 🗄️ SQLite | `.db`, `.sqlite`, `.sqlite3` | Built-in | Table schemas + latest 20 rows per table |
| 📊 Parquet | `.parquet` | pyarrow (optional) | Schema + row count *(metadata only)* |
| 🎨 Design | `.fig`, `.sketch`, `.xd` | Built-in | File size + page count *(metadata only)* |
| 💻 Code | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.sh`, ... | Direct mirror | Full content |
| 📋 Text | `.txt`, `.md`, `.json`, `.yml`, `.xml`, `.html`, `.css` | Direct mirror | Full content |
| 📦 Other | `*` | Fallback | MIME type + file metadata |

### ⚡ Intelligent Caching

Two-layer cache for instant incremental builds:
1. **Fast check** (mtime + size) — skip unchanged files in 0.003s
2. **Content check** (SHA-256) — detect true changes even if timestamp differs

Only files whose content has actually changed are re-extracted. The rest are instant cache hits.

### 📁 Directory Summaries

Auto-generated `.dir.meta` files let agents "browse" entire directories without reading every file:

```
project/.dir.meta       ← "What is this project?"
  src/.dir.meta         ← "What's in src/?"
  docs/.dir.meta        ← "What docs exist?"
```

### 🔒 Privacy & Security

- `.farignore` file (gitignore syntax) to exclude sensitive paths and directories
- Fully offline — no files leave your machine without API keys
- Selective extraction: mark directories as "metadata-only" (no content extraction)

---

## 📊 Why Not RAG?

RAG chunks documents into 500–1000 token fragments. This **destroys structure**:

```
Original table in report.pdf:
| Region  | Revenue | Growth |
| APAC    | $2.3M   | +28%   |   ← complete, meaningful
| NA      | $1.9M   | +12%   |

After RAG chunking:
  Chunk 37: "...APAC $2.3M +28% NA"
  Chunk 38: "$1.9M +12% Europe..."  ← table split, context lost
```

FAR preserves the full file structure in every `.meta`. The agent always gets the complete picture.

| | RAG | FAR |
|---|---|---|
| Infrastructure | 3+ always-running services | Zero |
| Content quality | Lossy chunks | Complete file |
| Binary support | Partial | Full |
| Latency | 200–500ms | <10ms |
| Offline | ❌ | ✅ |

## 🧠 Inspired by Unity Engine

In 2005, Unity faced the same problem — game assets (`.png`, `.fbx`, `.wav`) are binary and opaque to the engine. Their solution: **every asset gets a persistent text sidecar**.

```
player.png      →   player.png.meta   (Unity: engine metadata)
report.pdf      →   report.pdf.meta   (FAR: AI-readable content)
```

Twenty years later, FAR applies the same insight to AI coding agents.

## 🔌 Ecosystem Compatibility

FAR sits at the **file layer** of the AI infrastructure stack — complementing, not replacing, existing tools:

| Standard | Scope | Relationship to FAR |
|----------|-------|---------------------|
| `AGENTS.md` | Project instructions | Add one FAR rule |
| `llms.txt` | Site/project summary | FAR is per-file granularity |
| MCP | Tool/resource protocol | FAR can be exposed as MCP resource |
| RAG | Query-time retrieval | FAR provides clean, structured input |

---

## 📐 The `.meta` Format

```markdown
---
far_version: 1
source:
  sha256: a1b2c3d4...
  mime: application/pdf
  size: 129509
extract:
  pipeline: far_gen_v6
  extracted_at: 2026-02-27T10:00:00Z
---
# report.pdf

## Executive Summary
Revenue grew 23% YoY driven by APAC expansion.

## Table 1 - Revenue by Region
| Region       | Q3 2025 | Growth |
|--------------|---------|--------|
| Asia-Pacific | $2.3M   | +28%   |
| N. America   | $1.9M   | +12%   |
```

## 📖 Research

**[File-Augmented Retrieval: Making Every File Readable to Coding Agents via Persistent .meta Sidecars](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf)**

*Kelly Peilin Chan, 2026*

## 📚 Documentation

Full documentation in [`skills/far/SKILL.md`](skills/far/SKILL.md)

## 📄 License

MIT License

---

<div align="center">

**Built with ❤️ by [Kelly](https://github.com/mr-kelly)**

</div>
