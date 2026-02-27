#!/usr/bin/env python3
import os
import sys
import argparse
import hashlib
import mimetypes
import subprocess
import datetime
import zipfile
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import json
import base64
from pathlib import Path

# --- Configuration ---
SKILL_VERSION = "1.0.0"
PIPELINE_ID = "far_gen_v12"
MAX_DIR_SUMMARY_FILES = 50  # Max files to list in .dir.meta summary
FFMPEG_BIN = "/home/linuxbrew/.linuxbrew/bin/ffmpeg"
FFPROBE_BIN = "/home/linuxbrew/.linuxbrew/bin/ffprobe"
OPENAI_MODEL_AUDIO = "whisper-1"
OPENAI_MODEL_IMAGE = "gpt-4o-mini" # Use a cost-effective model for vision
MAX_AUDIO_MB = 25 # OpenAI API limit
LOG_FILE = os.path.expanduser("~/far.log")

def log(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] [{level}] {msg}"
    print(formatted_msg)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(formatted_msg + "\n")
    except: pass

def load_env(env_path):
    """Simple .env parser to avoid external dependencies."""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Strip quotes if present
                    value = value.strip().strip("'").strip('"')
                    os.environ[key.strip()] = value

# Load .env from skill directory or user home
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
load_env(os.path.join(SCRIPT_DIR, ".env"))
load_env(os.path.expanduser("~/.far.env"))

def get_openai_key():
    return os.environ.get("OPENAI_API_KEY")

def get_openai_base():
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

def get_sha256(filepath):
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None

def get_mime_type(filepath):
    """Guess MIME type."""
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type is None:
        try:
            result = subprocess.run(['file', '--mime-type', '-b', filepath], capture_output=True, text=True)
            mime_type = result.stdout.strip()
        except FileNotFoundError:
            mime_type = "application/octet-stream"
    return mime_type

# --- AI Extractors (Zero Dependency HTTP) ---

def openai_transcribe(filepath):
    """Transcribe audio/video using OpenAI Whisper API via standard library."""
    api_key = get_openai_key()
    if not api_key: return None

    # Check file size
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    
    # If file is too large or video, try to extract audio first using ffmpeg
    process_file = filepath
    temp_audio = None
    
    if file_size_mb > MAX_AUDIO_MB or get_mime_type(filepath).startswith('video/'):
        # Extract/Compress audio
        temp_audio = filepath + ".far_temp.mp3"
        ffmpeg_cmd = [FFMPEG_BIN if os.path.exists(FFMPEG_BIN) else 'ffmpeg', '-y', '-i', filepath, '-vn', '-ar', '16000', '-ac', '1', '-b:a', '32k', temp_audio]
        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            process_file = temp_audio
            # Check size again
            if os.path.getsize(process_file) / (1024 * 1024) > MAX_AUDIO_MB:
                if temp_audio: os.remove(temp_audio)
                return "[Error: Audio file too large for API even after compression]"
        except subprocess.CalledProcessError:
            if temp_audio and os.path.exists(temp_audio): os.remove(temp_audio)
            return None # Fallback to local metadata if ffmpeg fails
        except FileNotFoundError:
             return None # ffmpeg not found

    try:
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        data = []
        data.append(f'--{boundary}')
        data.append(f'Content-Disposition: form-data; name="model"')
        data.append('')
        data.append(OPENAI_MODEL_AUDIO)
        data.append(f'--{boundary}')
        data.append(f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(process_file)}"')
        data.append('Content-Type: application/octet-stream')
        data.append('')
        
        with open(process_file, 'rb') as f:
            file_data = f.read()
            
        body = b'\r\n'.join([x.encode('utf-8') for x in data]) + b'\r\n' + file_data + b'\r\n' + f'--{boundary}--'.encode('utf-8') + b'\r\n'

        req = urllib.request.Request(
            f"{get_openai_base()}/audio/transcriptions",
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': f'multipart/form-data; boundary={boundary}'
            }
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.load(response)
            return f"[AI Transcription ({OPENAI_MODEL_AUDIO})]:\n{result.get('text', '')}"

    except Exception as e:
        return f"[AI Transcription Error: {e}]"
    finally:
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)

def openai_vision(filepath):
    """Describe image using OpenAI Vision API."""
    api_key = get_openai_key()
    if not api_key: return None
    
    # Simple check: skip large images to save bandwidth/tokens
    if os.path.getsize(filepath) > 10 * 1024 * 1024: return None

    try:
        with open(filepath, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": OPENAI_MODEL_IMAGE,
            "messages": [
                {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in detail for a blind user. If it contains text, transcribe it."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
                }
            ],
            "max_tokens": 500
        }

        req = urllib.request.Request(
            f"{get_openai_base()}/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers=headers
        )

        with urllib.request.urlopen(req) as response:
            result = json.load(response)
            content = result['choices'][0]['message']['content']
            return f"[AI Vision Description ({OPENAI_MODEL_IMAGE})]:\n{content}"

    except Exception as e:
        return f"[AI Vision Error: {e}]"


# --- Local Extractors ---

def extract_pdf(filepath):
    try:
        result = subprocess.run(['pdftotext', '-layout', filepath, '-'], capture_output=True, text=True)
        text = result.stdout

        # Heuristic: If very little text, try OCR all pages
        if len(text.strip()) < 50:
            try:
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    subprocess.run(['pdftoppm', '-png', filepath, os.path.join(tmpdir, 'page')], capture_output=True)
                    pages = sorted(Path(tmpdir).glob('*.png'))
                    ocr_parts = []
                    for i, page in enumerate(pages, 1):
                        r = subprocess.run(['tesseract', str(page), '-', '-l', 'eng+chi_sim'], capture_output=True, text=True)
                        if r.returncode == 0 and r.stdout.strip():
                            ocr_parts.append(f"[Page {i}]:\n{r.stdout.strip()}")
                    if ocr_parts:
                        text = f"{text}\n\n[OCR Extraction]:\n" + "\n\n".join(ocr_parts)
            except FileNotFoundError:
                pass

        # Extract embedded images from PDF
        images_text = extract_pdf_images(filepath)
        if images_text:
            text = f"{text}\n\n{images_text}"

        return text if result.returncode == 0 else f"[Error: {result.stderr}]"
    except FileNotFoundError:
        return "[Error: pdftotext not installed]"


def extract_pdf_images(filepath):
    """Extract and OCR embedded images from a PDF using pdfimages."""
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ['pdfimages', '-png', filepath, os.path.join(tmpdir, 'img')],
                capture_output=True
            )
            if result.returncode != 0:
                return ""
            images = sorted(Path(tmpdir).glob('*.png'))
            if not images:
                return ""
            parts = ["## Embedded Images"]
            for i, img in enumerate(images[:10], 1):  # cap at 10 images
                ocr = ""
                try:
                    r = subprocess.run(['tesseract', str(img), '-', '-l', 'eng+chi_sim'], capture_output=True, text=True)
                    if r.returncode == 0 and r.stdout.strip():
                        ocr = r.stdout.strip()
                except FileNotFoundError:
                    pass
                ai = openai_vision(str(img))
                if ai or ocr:
                    parts.append(f"### Image {i}")
                    if ai:
                        parts.append(ai)
                    if ocr:
                        parts.append(f"[OCR]: {ocr}")
            return "\n".join(parts) if len(parts) > 1 else ""
    except FileNotFoundError:
        return ""  # pdfimages not installed, skip silently

def extract_docx(filepath):
    try:
        result = subprocess.run(['docx2txt', filepath, '-'], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"[Error: {result.stderr}]"
    except FileNotFoundError:
        return "[Error: docx2txt not installed]"

def extract_doc(filepath):
    try:
        result = subprocess.run(['antiword', filepath], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"[Error: {result.stderr}]"
    except FileNotFoundError:
        return "[Error: antiword not installed]"

def extract_xlsx(filepath):
    text_content = []
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                with z.open('xl/sharedStrings.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for t in root.iter():
                        if t.tag.endswith('t'): 
                            if t.text:
                                shared_strings.append(t.text)
            
            sheet_files = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')]
            sheet_files.sort()
            
            for file in sheet_files:
                sheet_name = file.split('/')[-1]
                text_content.append(f"## {sheet_name}")
                
                with z.open(file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    rows = []
                    for row in root.iter():
                        if row.tag.endswith('row'):
                            row_data = []
                            for cell in row.iter():
                                if cell.tag.endswith('c'):
                                    cell_type = cell.get('t')
                                    val = None
                                    for v in cell.iter():
                                        if v.tag.endswith('v'):
                                            val = v.text
                                            break
                                    if val:
                                        if cell_type == 's': 
                                            try:
                                                idx = int(val)
                                                if idx < len(shared_strings):
                                                    val = shared_strings[idx]
                                            except ValueError: pass
                                        row_data.append(str(val))
                            if row_data:
                                rows.append(" | ".join(row_data))
                    if rows:
                        text_content.append("\n".join(rows))
                    else:
                        text_content.append("(Empty Sheet)")
                    text_content.append("\n")
        return "\n".join(text_content)
    except Exception as e:
        return f"[Error extracting XLSX (native mode): {e}]"

def extract_pptx(filepath):
    text_content = []
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            slides = [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
            slides.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))

            for i, slide in enumerate(slides):
                text_content.append(f"## Slide {i+1}")
                slide_text = []
                with z.open(slide) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for elem in root.iter():
                        if elem.tag.endswith('t'):
                            if elem.text:
                                slide_text.append(elem.text)
                if slide_text:
                    text_content.append("\n".join(slide_text))
                else:
                    text_content.append("(No text)")
                text_content.append("\n")
        return "\n".join(text_content)
    except Exception as e:
        return f"[Error extracting PPTX (native mode): {e}]"


def extract_epub(filepath):
    """Extract text from EPUB by reading HTML content files."""
    try:
        import re
        parts = []
        with zipfile.ZipFile(filepath, 'r') as z:
            opf_files = [f for f in z.namelist() if f.endswith('.opf')]
            spine_items = []
            if opf_files:
                with z.open(opf_files[0]) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    manifest = {item.get('id'): item.get('href')
                                for item in root.findall('.//{http://www.idpf.org/2007/opf}item')}
                    for itemref in root.findall('.//{http://www.idpf.org/2007/opf}itemref'):
                        idref = itemref.get('idref')
                        if idref in manifest:
                            spine_items.append(manifest[idref])
            if not spine_items:
                spine_items = [f for f in z.namelist() if f.endswith(('.html', '.xhtml', '.htm'))]
            base = (os.path.dirname(opf_files[0]) + '/') if opf_files else ''
            for item in spine_items[:50]:
                path = (base + item).lstrip('/')
                if path not in z.namelist():
                    path = item
                if path not in z.namelist():
                    continue
                with z.open(path) as f:
                    content = f.read().decode('utf-8', errors='ignore')
                text = re.sub(r'<[^>]+>', ' ', content)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    parts.append(text)
        return "\n\n".join(parts) if parts else "[Empty EPUB]"
    except Exception as e:
        return f"[Error extracting EPUB: {e}]"


def extract_zip(filepath):
    """List contents of a ZIP/archive file."""
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            entries = z.infolist()
            lines = [f"## Archive Contents ({len(entries)} files)\n"]
            for entry in entries[:200]:
                size = f"{entry.file_size:,} bytes" if entry.file_size else "dir"
                lines.append(f"- `{entry.filename}` ({size})")
            if len(entries) > 200:
                lines.append(f"\n*({len(entries)} total, showing first 200)*")
            return "\n".join(lines)
    except Exception as e:
        return f"[Error reading archive: {e}]"


def extract_csv(filepath):
    try:
        import csv
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return "(Empty CSV)"
        header = rows[0]
        lines = ["| " + " | ".join(header) + " |",
                 "| " + " | ".join(["---"] * len(header)) + " |"]
        for row in rows[1:101]:  # cap at 100 rows
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        if len(rows) > 101:
            lines.append(f"\n*({len(rows) - 1} rows total, showing first 100)*")
        return "\n".join(lines)
    except Exception as e:
        return f"[Error extracting CSV: {e}]"


def extract_ipynb(filepath):
    """Extract Jupyter Notebook: markdown cells + code cells + outputs."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            nb = json.load(f)
        parts = []
        for i, cell in enumerate(nb.get('cells', [])):
            ctype = cell.get('cell_type', '')
            source = ''.join(cell.get('source', []))
            if ctype == 'markdown':
                parts.append(source)
            elif ctype == 'code':
                parts.append(f"```python\n{source}\n```")
                for output in cell.get('outputs', []):
                    otype = output.get('output_type', '')
                    if otype in ('stream', 'execute_result', 'display_data'):
                        text = output.get('text') or output.get('data', {}).get('text/plain', [])
                        out = ''.join(text) if isinstance(text, list) else str(text)
                        if out.strip():
                            parts.append(f"**Output:**\n```\n{out.strip()}\n```")
        return "\n\n".join(parts)
    except Exception as e:
        return f"[Error extracting notebook: {e}]"


def extract_media_metadata(filepath, mime_type):
    """Extract duration, format info, and process Video/Audio based on FAR_VIDEO_MODE."""
    mode = os.environ.get("FAR_VIDEO_MODE", "A").upper()
    if mode == "ALL": mode = "D"
    
    parts = []
    
    # 1. Base ffprobe metadata
    local_info = ""
    import shutil
    try:
        if not os.path.exists(FFPROBE_BIN) and shutil.which('ffprobe') is None:
             local_info = "[ffprobe not found]"
        else:
            cmd = [FFPROBE_BIN, '-v', 'error', '-show_entries', 'format=duration,size,bit_rate:stream=codec_name,width,height', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
            if not os.path.exists(FFPROBE_BIN): cmd[0] = 'ffprobe'

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                local_info = f"Media Info (ffprobe):\n{result.stdout}"
    except Exception as e:
        local_info = f"[Media extraction error: {e}]"
    parts.append(local_info)

    # 2. Audio Processing (Option B) - Applies to both audio/video files
    if mode in ["B", "D"] or mime_type.startswith('audio/'):
        ai_transcript = openai_transcribe(filepath)
        if ai_transcript:
            parts.append(f"## Audio Transcript (Option B)\n{ai_transcript}")

    # 3. Video Processing (Option A & C)
    if mime_type.startswith('video/') and mode in ["A", "C", "D"]:
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract 1 frame per 3 seconds (max 20 frames to avoid hanging)
                cmd = [FFMPEG_BIN if os.path.exists(FFMPEG_BIN) else 'ffmpeg', '-y', '-i', filepath, '-vf', 'fps=1/3', '-vframes', '20', os.path.join(tmpdir, 'frame_%04d.png')]
                subprocess.run(cmd, capture_output=True)
                
                frames = sorted(Path(tmpdir).glob('*.png'))
                if frames:
                    # Option A: Local OCR (Default)
                    if mode in ["A", "D"]:
                        ocr_texts = []
                        seen_lines = set()
                        for f in frames:
                            try:
                                r = subprocess.run(['tesseract', str(f), 'stdout', '-l', 'chi_sim+eng'], capture_output=True, text=True)
                                if r.returncode == 0:
                                    text = r.stdout.strip()
                                    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 2]
                                    new_lines = []
                                    for l in lines:
                                        if l not in seen_lines:
                                            seen_lines.add(l)
                                            new_lines.append(l)
                                    if new_lines:
                                        ocr_texts.append("\n".join(new_lines))
                            except Exception:
                                pass
                        if ocr_texts:
                            parts.append("## Video Frame OCR (Option A)\n" + "\n...\n".join(ocr_texts))
                    
                    # Option C: Vision API
                    if mode in ["C", "D"]:
                        api_key = get_openai_key()
                        if api_key:
                            selected_frames = frames[::max(1, len(frames)//5)][:5] # Up to 5 evenly spaced frames
                            images_content = []
                            for f in selected_frames:
                                with open(f, "rb") as image_file:
                                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                                images_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}})
                                
                            try:
                                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
                                payload = {
                                    "model": OPENAI_MODEL_IMAGE,
                                    "messages": [{"role": "user", "content": [{"type": "text", "text": "Describe the sequence of events and any text visible in these video frames."}] + images_content}],
                                    "max_tokens": 1000
                                }
                                import urllib.request
                                import json
                                req = urllib.request.Request(f"{get_openai_base()}/chat/completions", data=json.dumps(payload).encode('utf-8'), headers=headers)
                                with urllib.request.urlopen(req) as response:
                                    res = json.load(response)
                                    content_vision = res['choices'][0]['message']['content']
                                    parts.append(f"## AI Vision Summary (Option C)\n{content_vision}")
                            except Exception as e:
                                parts.append(f"[AI Vision Error: {e}]")
        except Exception as e:
            parts.append(f"[Video frame processing error: {e}]")

    return "\n\n".join(parts)

    
def extract_image_ocr(filepath):
    """Extract text from image using tesseract (local) + AI Vision (optional)."""
    local_ocr = ""
    try:
        subprocess.run(['tesseract', '--version'], capture_output=True, check=False)
        result = subprocess.run(['tesseract', filepath, '-', '-l', 'eng+chi_sim'], capture_output=True, text=True)
        if result.returncode == 0:
             local_ocr = f"[Local OCR]:\n{result.stdout}"
    except FileNotFoundError:
        local_ocr = "[Error: tesseract not installed]"

    # AI Enhancement
    ai_vision = openai_vision(filepath)
    if ai_vision:
        return f"{local_ocr}\n\n{ai_vision}"
    return local_ocr


def extract_tar(filepath):
    """List contents of a tar/tar.gz/tar.bz2 archive."""
    try:
        import tarfile
        with tarfile.open(filepath, 'r:*') as t:
            members = t.getmembers()
            lines = [f"## Archive Contents ({len(members)} entries)\n"]
            for m in members[:200]:
                size = f"{m.size:,} bytes" if m.isfile() else "dir"
                lines.append(f"- `{m.name}` ({size})")
            if len(members) > 200:
                lines.append(f"\n*({len(members)} total, showing first 200)*")
            return "\n".join(lines)
    except Exception as e:
        return f"[Error reading archive: {e}]"


def extract_eml(filepath):
    """Extract email content: headers + body + attachment list."""
    try:
        import email
        with open(filepath, 'rb') as f:
            msg = email.message_from_bytes(f.read())
        parts = []
        parts.append(f"**From:** {msg.get('From', '')}")
        parts.append(f"**To:** {msg.get('To', '')}")
        parts.append(f"**Subject:** {msg.get('Subject', '')}")
        parts.append(f"**Date:** {msg.get('Date', '')}")
        parts.append("")
        attachments = []
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            if 'attachment' in cd:
                attachments.append(part.get_filename() or 'unnamed')
            elif ct == 'text/plain' and 'attachment' not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode('utf-8', errors='ignore'))
            elif ct == 'text/html' and 'attachment' not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    import re
                    text = re.sub(r'<[^>]+>', ' ', payload.decode('utf-8', errors='ignore'))
                    text = re.sub(r'\s+', ' ', text).strip()
                    parts.append(text)
        if attachments:
            parts.append(f"\n**Attachments:** {', '.join(attachments)}")
        return "\n".join(parts)
    except Exception as e:
        return f"[Error extracting email: {e}]"


def extract_rtf(filepath):
    """Extract plain text from RTF by stripping control words."""
    try:
        import re
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Remove RTF control words and groups
        text = re.sub(r'\\[a-z]+[-]?\d*[ ]?', '', content)
        text = re.sub(r'[{}\\]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        return f"[Error extracting RTF: {e}]"


def extract_sqlite(filepath):
    """Extract table schemas and recent rows from SQLite (up to 20 rows per table)."""
    MAX_ROWS = 20
    try:
        import sqlite3
        con = sqlite3.connect(filepath)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        parts = [f"## SQLite Database\n\n**Tables:** {len(tables)}"]
        for table in tables:
            try:
                cur.execute(f"PRAGMA table_info(`{table}`)")
                col_info = cur.fetchall()
                cols = [r[1] for r in col_info]
                col_types = [f"`{r[1]}` {r[2]}" for r in col_info]
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = cur.fetchone()[0]
                parts.append(f"### {table} ({count:,} rows)\n**Schema:** " + ", ".join(col_types))
                # Fetch most recent rows by rowid desc
                cur.execute(f"SELECT * FROM `{table}` ORDER BY rowid DESC LIMIT {MAX_ROWS}")
                rows = cur.fetchall()
                if rows:
                    header = "| " + " | ".join(cols) + " |"
                    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
                    lines = [header, sep]
                    for row in reversed(rows):  # show oldest-first within the sample
                        lines.append("| " + " | ".join(str(v) if v is not None else "" for v in row) + " |")
                    parts.append("\n".join(lines))
                    if count > MAX_ROWS:
                        parts.append(f"*({count:,} rows total, showing latest {MAX_ROWS})*")
            except Exception as ex:
                parts.append(f"### {table} (error: {ex})")
        con.close()
        return "\n\n".join(parts)
    except Exception as e:
        return f"[Error extracting SQLite: {e}]"


def extract_parquet(filepath):
    """[Metadata only] Extract schema and row count from Parquet file."""
    try:
        import struct
        # Read Parquet footer magic to confirm format, then use pyarrow if available
        try:
            import pyarrow.parquet as pq
            pf = pq.read_metadata(filepath)
            schema = pq.read_schema(filepath)
            fields = [f"`{f.name}` {f.type}" for f in schema]
            parts = [
                f"## Parquet File",
                f"**Rows:** {pf.num_rows:,}  **Row groups:** {pf.num_row_groups}  **Columns:** {len(fields)}",
                "\n### Schema\n" + "\n".join(f"- {f}" for f in fields),
                "\n> [Metadata only] — row content not extracted.",
            ]
            return "\n\n".join(parts)
        except ImportError:
            return "[Metadata only] Parquet file detected. Install `pyarrow` for schema extraction."
    except Exception as e:
        return f"[Error extracting Parquet: {e}]"


def extract_design_metadata(filepath):
    """[Metadata only] Extract basic metadata from .fig / .sketch / .xd design files."""
    try:
        stat = os.stat(filepath)
        ext = Path(filepath).suffix.lower()
        name = Path(filepath).name
        size_kb = stat.st_size / 1024
        # .sketch and .fig are zip-based, try to list internal structure
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                entries = z.namelist()
                pages = [e for e in entries if 'page' in e.lower() or 'canvas' in e.lower()]
                parts = [
                    f"## {name}",
                    f"**Format:** {ext[1:].upper()}  **Size:** {size_kb:.1f} KB",
                    f"**Internal files:** {len(entries)}",
                ]
                if pages:
                    parts.append(f"**Pages/Canvases:** {len(pages)}")
                parts.append("\n> [Metadata only] — design content requires native app to render.")
                return "\n\n".join(parts)
        except Exception:
            return (f"## {name}\n\n**Format:** {ext[1:].upper()}  **Size:** {size_kb:.1f} KB"
                    "\n\n> [Metadata only] — design content requires native app to render.")
    except Exception as e:
        return f"[Error reading design file: {e}]"


# --- Ignorer ---

def load_farignore(root_dir):
    ignore_patterns = ['.git', '.meta', '.DS_Store', 'node_modules']
    ignore_path = os.path.join(root_dir, '.farignore')
    if os.path.exists(ignore_path):
        with open(ignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.append(line)
    return ignore_patterns

def should_ignore(path, root_dir, ignore_patterns):
    import fnmatch
    rel_path = os.path.relpath(path, root_dir).replace(os.sep, '/')
    parts = rel_path.split('/')
    for pattern in ignore_patterns:
        p = pattern.rstrip('/')
        # Match any path component
        if p in parts:
            return True
        # Full glob match
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern.rstrip('/') + '/*'):
            return True
        # Match each component
        for part in parts:
            if fnmatch.fnmatch(part, p):
                return True
    return False

# --- Generators ---

def generate_file_meta(filepath, root_dir, ignore_patterns, force=False):
    if should_ignore(filepath, root_dir, ignore_patterns):
        return None

    file_path = Path(filepath)
    meta_path = file_path.with_suffix(file_path.suffix + ".meta")
    
    # 1. Fast Check: Mtime & Size
    try:
        stat = os.stat(filepath)
        current_mtime = stat.st_mtime
        current_size = stat.st_size
    except FileNotFoundError:
        log(f"Error: File not found {filepath}", "ERROR")
        return None

    if not force and meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if (f"mtime: {current_mtime}" in content
                    and f"size: {current_size}" in content
                    and f"pipeline: {PIPELINE_ID}" in content):
                return meta_path
        except Exception:
            pass

    # 2. Slow Check: SHA256 (if mtime/size/pipeline changed)
    current_hash = get_sha256(filepath)
    if not current_hash:
        log(f"Error: Cannot hash {filepath}", "ERROR")
        return None

    # Check SHA256 even if mtime changed (content may be same)
    if not force and meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if (f"sha256: {current_hash}" in content
                    and f"pipeline: {PIPELINE_ID}" in content):
                # Content unchanged, just update mtime in meta
                updated = content.replace(
                    next(l for l in content.splitlines() if l.strip().startswith('mtime:')),
                    f"  mtime: {current_mtime}"
                )
                with open(meta_path, 'w', encoding='utf-8') as f:
                    f.write(updated)
                return meta_path
        except Exception:
            pass

    # Extract
    log(f"Processing: {filepath} ({current_hash[:8]}...)")
    mime_type = get_mime_type(filepath)
    ext = file_path.suffix.lower()
    extracted_text = ""
    layout = {}
    start_time = datetime.datetime.now()

    if ext == '.pdf':
        extracted_text = extract_pdf(filepath)
        # Count pages
        try:
            r = subprocess.run(['pdfinfo', filepath], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if line.startswith('Pages:'):
                    layout['pages'] = int(line.split(':')[1].strip())
        except Exception:
            pass
    elif ext == '.docx': extracted_text = extract_docx(filepath)
    elif ext == '.doc': extracted_text = extract_doc(filepath)
    elif ext == '.xlsx':
        extracted_text = extract_xlsx(filepath)
        # Count sheets
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                sheets = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')]
                layout['sheets'] = len(sheets)
        except Exception:
            pass
    elif ext == '.pptx':
        extracted_text = extract_pptx(filepath)
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                slides = [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
                layout['slides'] = len(slides)
        except Exception:
            pass
    elif ext == '.csv': extracted_text = extract_csv(filepath)
    elif ext == '.ipynb': extracted_text = extract_ipynb(filepath)
    elif ext == '.epub': extracted_text = extract_epub(filepath)
    elif ext in ('.zip', '.jar', '.whl', '.apk'): extracted_text = extract_zip(filepath)
    elif ext in ('.tar', '.gz', '.bz2', '.xz', '.tgz'): extracted_text = extract_tar(filepath)
    elif ext in ('.eml', '.msg'): extracted_text = extract_eml(filepath)
    elif ext == '.rtf': extracted_text = extract_rtf(filepath)
    elif ext in ('.db', '.sqlite', '.sqlite3'): extracted_text = extract_sqlite(filepath)
    elif ext == '.parquet': extracted_text = extract_parquet(filepath)
    elif ext in ('.fig', '.sketch', '.xd'): extracted_text = extract_design_metadata(filepath)
    elif mime_type.startswith('image/'): extracted_text = extract_image_ocr(filepath)
    elif mime_type.startswith('video/') or mime_type.startswith('audio/'): extracted_text = extract_media_metadata(filepath, mime_type)
    elif mime_type.startswith('text/') or ext in ['.txt', '.md', '.json', '.yml', '.py', '.sh', '.meta', '.js', '.css', '.html', '.xml']:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
        except: extracted_text = "[Read Error]"
    else:
        extracted_text = f"[Binary: {mime_type}]"

    duration = (datetime.datetime.now() - start_time).total_seconds()
    log(f"Done: {filepath} (Time: {duration:.2f}s)")


    # Write .meta
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    layout_yaml = ""
    if layout:
        layout_yaml = "layout:\n" + "".join(f"  {k}: {v}\n" for k, v in layout.items())
    meta_content = f"""--far_version: 1
source:
  sha256: {current_hash}
  mime: {mime_type}
  size: {current_size}
  mtime: {current_mtime}
extract:
  pipeline: {PIPELINE_ID}
  extracted_at: {timestamp}
  deterministic: true
{layout_yaml}---
# {file_path.name}

{extracted_text}
"""
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write(meta_content)
    
    log(f"Generated meta: {meta_path}", "DEBUG")
    return meta_path

def generate_dir_meta(dirpath, root_dir, ignore_patterns, files_in_dir):
    if should_ignore(dirpath, root_dir, ignore_patterns): return

    meta_path = os.path.join(dirpath, ".dir.meta")
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    summary_lines = []
    summary_lines.append(f"# Directory: {os.path.basename(dirpath)}")
    summary_lines.append(f"Contains {len(files_in_dir)} files processed by FAR.\n")
    
    count = 0
    for file, f_meta_path in files_in_dir:
        if count >= MAX_DIR_SUMMARY_FILES:
            summary_lines.append(f"\n... and {len(files_in_dir) - count} more files.")
            break
        
        snippet = ""
        try:
            with open(f_meta_path, 'r', encoding='utf-8') as f:
                content = f.read()
                parts = content.split('\n---\n')
                if len(parts) >= 2:
                    body = parts[-1].strip()
                    lines = body.splitlines()
                    if lines and lines[0].startswith('# '):
                        body = "\n".join(lines[1:]).strip()
                    clean_body = " ".join(body.split())[:150]
                    if clean_body: snippet = clean_body + "..."
        except: pass
        
        summary_lines.append(f"- **{file}**: {snippet}")
        count += 1

    meta_content = f"""--far_version: 1
type: directory
extract:
  pipeline: {PIPELINE_ID}
  extracted_at: {timestamp}
---
{chr(10).join(summary_lines)}
"""
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write(meta_content)
    log(f"Generated dir.meta: {meta_path}", "DEBUG")

def main():
    parser = argparse.ArgumentParser(description="Generate .meta sidecar files for AI readability (FAR protocol).")
    parser.add_argument("path", nargs="?", default=".", help="Target directory or file to scan")
    parser.add_argument("--force", action="store_true", help="Force regenerate .meta files even if unchanged")
    args = parser.parse_args()
        
    target_path = os.path.abspath(args.path)
    
    # Handle single file case
    if os.path.isfile(target_path):
        root_dir = os.path.dirname(target_path)
        ignore_patterns = load_farignore(root_dir)
        generate_file_meta(target_path, root_dir, ignore_patterns, force=args.force)
        return

    if not os.path.isdir(target_path):
        log(f"Error: {target_path} is not a directory or file", "ERROR")
        sys.exit(1)

    ignore_patterns = load_farignore(target_path)
    log(f"FAR scanning: {target_path} (Ignore: {ignore_patterns})")

    for root, dirs, files in os.walk(target_path, topdown=False):
        if should_ignore(root, target_path, ignore_patterns): continue

        processed_files = []
        
        # --- Cleanup orphaned .meta files ---
        for file in files:
            if file.endswith('.meta') and file != '.dir.meta':
                original_file = file[:-5]
                if original_file not in files:
                    orphan_path = os.path.join(root, file)
                    try:
                        os.remove(orphan_path)
                        log(f"Cleaned up orphaned meta: {orphan_path}")
                    except Exception as e:
                        pass
        # ------------------------------------

        for file in files:
            if file.endswith('.meta') or file.startswith('.'): continue
            
            file_path = os.path.join(root, file)
            meta_path = generate_file_meta(file_path, target_path, ignore_patterns, force=args.force)
            if meta_path:
                processed_files.append((file, meta_path))
        
        if processed_files:
            generate_dir_meta(root, target_path, ignore_patterns, processed_files)

if __name__ == "__main__":
    main()
