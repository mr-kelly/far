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
SKILL_VERSION = "0.6.0"
PIPELINE_ID = "far_gen_v7"
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

        # Heuristic: If very little text, try OCR (local)
        if len(text.strip()) < 50:
            try:
                ppm_proc = subprocess.Popen(['pdftoppm', '-png', '-f', '1', '-l', '1', filepath], stdout=subprocess.PIPE)
                tess_proc = subprocess.run(['tesseract', '-', '-', '-l', 'eng+chi_sim'], stdin=ppm_proc.stdout, capture_output=True, text=True)
                ocr_text = tess_proc.stdout
                if ocr_text.strip():
                    text = f"{text}\n\n[Local OCR Extraction (Page 1)]:\n{ocr_text}"
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


def extract_csv(filepath):
    """Extract CSV as a Markdown table."""
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


def extract_media_metadata(filepath):
    """Extract duration and format info using ffprobe."""
    local_info = ""
    try:
        # Check if ffprobe exists
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

    # AI Enhancement
    ai_transcript = openai_transcribe(filepath)
    if ai_transcript:
        return f"{local_info}\n\n{ai_transcript}"
    return local_info
    
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
    rel_path = os.path.relpath(path, root_dir)
    for pattern in ignore_patterns:
        if pattern in rel_path.split(os.sep): return True
        if pattern.endswith('*') and pattern[:-1] in rel_path: return True
        if pattern.startswith('*') and rel_path.endswith(pattern[1:]): return True
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
                has_mtime = f"mtime: {current_mtime}" in content
                has_size = f"size: {current_size}" in content
                has_pipeline = f"pipeline: {PIPELINE_ID}" in content
                
                if has_mtime and has_size and has_pipeline:
                    return meta_path 
        except Exception: 
            pass

    # 2. Slow Check: SHA256 (if mtime changed or force=True)
    current_hash = get_sha256(filepath)
    if not current_hash: 
        log(f"Error: Cannot hash {filepath}", "ERROR")
        return None

    # Extract
    log(f"Processing: {filepath} ({current_hash[:8]}...)")
    mime_type = get_mime_type(filepath)
    ext = file_path.suffix.lower()
    extracted_text = ""
    start_time = datetime.datetime.now()

    if ext == '.pdf': extracted_text = extract_pdf(filepath)
    elif ext == '.docx': extracted_text = extract_docx(filepath)
    elif ext == '.doc': extracted_text = extract_doc(filepath)
    elif ext == '.xlsx': extracted_text = extract_xlsx(filepath)
    elif ext == '.pptx': extracted_text = extract_pptx(filepath)
    elif ext == '.csv': extracted_text = extract_csv(filepath)
    elif ext == '.ipynb': extracted_text = extract_ipynb(filepath)
    elif mime_type.startswith('image/'): extracted_text = extract_image_ocr(filepath)
    elif mime_type.startswith('video/') or mime_type.startswith('audio/'): extracted_text = extract_media_metadata(filepath)
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
    meta_content = f"""--far_version: 1
source:
  sha256: {current_hash}
  mime: {mime_type}
  size: {current_size}
  mtime: {current_mtime}
extract:
  pipeline: {PIPELINE_ID}
  extracted_at: {timestamp}
---
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
