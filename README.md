<div align="center">

# 📄 FAR - File-Augmented Retrieval

**Making Every File Readable to AI Coding Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](https://github.com/mr-kelly/far)

[📖 Read the Paper](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf) • [🚀 Quick Start](#-quick-start) • [✨ Features](#-features)

</div>

---

## 🎯 The Problem

AI coding agents can read code, but they're **blind to 30-40% of critical context** stored in binary formats:

- 📊 **Spreadsheets** (`budget.xlsx`)
- 📄 **Documents** (`requirements.docx`)  
- 🖼️ **Images** (`architecture.png`)
- 📑 **PDFs** (`contract.pdf`)

When an agent encounters these files, it sees opaque bytes. **It cannot reason about the content.**

## 💡 The Solution

FAR generates persistent `.meta` sidecar files that make binary documents readable:

```
project/
├── budget.xlsx         ← Binary (opaque)
└── budget.xlsx.meta    ← Markdown (readable by AI)
```

**No vector database. No API calls. No runtime overhead.**  
Just plain text files that live alongside your documents.

## ✨ Features

### 📦 Broad Format Support

- **📄 PDF** - Full text extraction + OCR for scanned documents
- **📝 Word/Excel/PowerPoint** - Text and table extraction  
- **🖼️ Images** - OCR (Tesseract) + AI Vision (GPT-4o)
- **🎬 Media** - Metadata + AI Transcription (Whisper)
- **💻 Code/Text** - Direct content mirroring

### ⚡ Intelligent Caching

Two-layer caching for instant incremental builds:
1. **Fast Check** (mtime & size) - Skip unchanged files in 0.003s
2. **Content Check** (SHA256) - Detect true changes even if timestamp differs

### 📁 Directory Summaries

Auto-generated `.dir.meta` files provide high-level overviews, letting agents "browse" folders efficiently.

### 🔗 Git LFS Support

Automatically handles Git LFS pointer files by pulling real content before processing.

## 🚀 Quick Start

### Installation

**For Claude Code:**
```bash
/plugin marketplace add mr-kelly/far
/plugin install mr-kelly-far
```

**For other AI agents (via npx):**
```bash
npx skills add mr-kelly/far
```

### Usage

```bash
# Scan current directory (recursive)
far

# Scan specific directory
far ~/Documents/projects/files

# Process single file
far report.pdf

# Force regeneration (ignore cache)
far . --force
```

### Configuration

Enable AI features (transcription, vision) by creating `.env`:

```bash
cp skills/far/.env.example skills/far/.env
# Add your OPENAI_API_KEY
```

Without API keys, FAR gracefully falls back to local tools (Tesseract, FFprobe).

## 📚 Documentation

Full documentation available in [`skills/far/SKILL.md`](skills/far/SKILL.md)

## 📖 Research

FAR is based on the research paper:

**[File-Augmented Retrieval: Making Every File Readable to Coding Agents via Persistent .meta Sidecars](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf)**

*Kelly Peilin Chan, 2026*

## 🤝 Contributing

Contributions welcome! This project follows the standard GitHub flow.

## 📄 License

MIT License - see LICENSE file for details

---

<div align="center">

**Built with ❤️ by [Kelly](https://github.com/mr-kelly)**

</div>
