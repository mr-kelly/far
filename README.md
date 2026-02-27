<div align="center">

# 📄 FAR - File-Augmented Retrieval

**Making Every File Readable to AI Coding Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](https://github.com/mr-kelly/far)

[📖 Read the Paper](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf) • [🚀 Quick Start](#-quick-start) • [✨ Features](#-features)

</div>

---

> *"RAG performs retrieval at query time. FAR performs augmentation at file time."*
> — [FAR Paper, Kelly Peilin Chan, 2026](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf)

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

FAR generates a persistent `.meta` sidecar next to every binary file — containing the full extracted content as Markdown:

```
project/
├── budget.xlsx           ← Binary (opaque to AI)
├── budget.xlsx.meta      ← Markdown table (readable by AI)
├── architecture.png      ← Binary
├── architecture.png.meta ← Caption + OCR text
└── standup.mp4.meta      ← Full transcript + topics
```

**No vector database. No embedding service. No runtime pipeline.**
The agent simply reads the `.meta` file directly from the filesystem.

## 📊 Why Not RAG?

RAG has three structural problems FAR solves:

| | RAG | FAR |
|---|---|---|
| Infrastructure | 3+ always-running services | Zero |
| Content quality | Lossy chunks (~500 tokens) | Complete file |
| Binary support | Partial | Full |
| Latency | 200–500ms | <10ms |
| Offline support | ❌ | ✅ |

**Benchmark on 10,000-file heterogeneous corpus:**

| Method | File Discovery | Cross-file Reasoning |
|--------|---------------|---------------------|
| grep | 31.2% | — |
| RAG (LangChain) | 58.7% | 34.1% |
| Vector + rerank | 52.1% | 41.3% |
| **FAR (.meta)** | **82.6%** | **71.9%** |

Storage overhead: only **6.3%** (146 MB on a 2.3 GB corpus, vs 890 MB for RAG).

## 🧠 Inspired by Unity Engine

FAR is inspired by Unity's `.meta` asset pipeline — a 20-year-old insight that every binary asset needs a text sidecar for the engine to understand it. FAR applies the same principle to AI coding agents.

```
player.png      →   player.png.meta   (Unity: engine metadata)
report.pdf      →   report.pdf.meta   (FAR: AI-readable content)
```

## ✨ Features

### 📦 Broad Format Support

| Format | Extractor | Output |
|--------|-----------|--------|
| 📄 PDF | pdfminer + tabula | Full text, tables as Markdown |
| 🖼️ Images | Tesseract OCR + GPT-4V | Caption + OCR text |
| 📊 Excel | openpyxl | Sheets as Markdown tables |
| 📝 Word/PowerPoint | python-docx | Full text |
| 🎬 Video/Audio | Whisper + ffmpeg | Transcript + topics |
| 💻 Code/Text | Direct mirror | Full content |

### ⚡ Intelligent Caching

Two-layer cache for instant incremental builds:
1. **Fast check** (mtime + size) — skip unchanged files in 0.003s
2. **Content check** (SHA-256) — detect true changes even if timestamp differs

On a 10,000-file repo with 50 changed files → only 50 extraction calls.

### 📁 Directory Summaries

Auto-generated `.dir.meta` files let agents "browse" entire directories:

```
project/.dir.meta       ← "What is this project?"
  src/.dir.meta         ← "What's in src/?"
  docs/.dir.meta        ← "What docs exist?"
```

### 🔒 Privacy & Security

- `.farignore` file (gitignore syntax) to exclude sensitive paths
- PII redaction rules configurable
- Encrypted sidecar support (content encrypted, YAML header plaintext)
- Fully offline — no files leave your machine

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

### One Rule for Your Agent

Add this to `AGENTS.md` or your system prompt — that's all:

```markdown
When you encounter a binary file you cannot read
(.png, .pdf, .xlsx, .mp4), check for a .meta file
beside it. The .meta contains extracted content as
Markdown. For directory overviews, read .dir.meta.
```

### Configuration

Enable AI features (vision, transcription) by creating `.env`:

```bash
cp skills/far/.env.example skills/far/.env
# Add your OPENAI_API_KEY
```

Without API keys, FAR gracefully falls back to local tools (Tesseract, FFprobe).

## 📐 The `.meta` Format

Every `.meta` file has a YAML frontmatter header + Markdown body:

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

## 📚 Documentation

Full documentation in [`skills/far/SKILL.md`](skills/far/SKILL.md)

## 📖 Research

Based on the research paper:

**[File-Augmented Retrieval: Making Every File Readable to Coding Agents via Persistent .meta Sidecars](https://mr-kelly.github.io/research/File-Augmented%20Retrieval%20-%20Making%20Every%20File%20Readable%20to%20Coding%20Agents%20via%20Persistent%20.meta%20Sidecars.pdf)**

*Kelly Peilin Chan, 2026*

Key findings:
- **82.6%** file-discovery accuracy vs 58.7% for RAG
- **71.9%** cross-file reasoning accuracy vs 34.1% for RAG
- **6.3%** storage overhead (vs 38.7% for RAG)
- **Zero** runtime infrastructure required

## 📄 License

MIT License

---

<div align="center">

**Built with ❤️ by [Kelly](https://github.com/mr-kelly)**

</div>
