import unittest
import os
import shutil
import tempfile
import sys
import sqlite3
import zipfile
import tarfile
import csv
import json
import io
from pathlib import Path

skill_dir = Path(__file__).parent.parent / "skills" / "far"
sys.path.insert(0, str(skill_dir))
import far_gen


class TestFormats(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def _file(self, name, content, mode="w"):
        p = os.path.join(self.d, name)
        with open(p, mode) as f:
            f.write(content)
        return p

    # --- CSV ---
    def test_csv(self):
        p = self._file("data.csv", "Name,Age\nAlice,30\nBob,25\n")
        result = far_gen.extract_csv(p)
        self.assertIn("| Name | Age |", result)
        self.assertIn("Alice", result)

    def test_csv_cap(self):
        rows = "id,val\n" + "".join(f"{i},{i*2}\n" for i in range(150))
        p = self._file("big.csv", rows)
        result = far_gen.extract_csv(p)
        self.assertIn("150 rows total", result)

    # --- SQLite ---
    def test_sqlite_schema_and_data(self):
        p = os.path.join(self.d, "test.db")
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE items (id INTEGER, name TEXT)")
        for i in range(5):
            con.execute("INSERT INTO items VALUES (?, ?)", (i, f"item{i}"))
        con.commit(); con.close()
        result = far_gen.extract_sqlite(p)
        self.assertIn("items", result)
        self.assertIn("id", result)
        self.assertIn("item0", result)

    def test_sqlite_cap(self):
        p = os.path.join(self.d, "big.db")
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE t (x INTEGER)")
        con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(30)])
        con.commit(); con.close()
        result = far_gen.extract_sqlite(p)
        self.assertIn("30 rows", result)
        self.assertIn("showing latest 20", result)

    # --- ZIP ---
    def test_zip(self):
        p = os.path.join(self.d, "archive.zip")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("README.md", "hello")
            z.writestr("src/main.py", "print(1)")
        result = far_gen.extract_zip(p)
        self.assertIn("README.md", result)
        self.assertIn("src/main.py", result)

    # --- TAR ---
    def test_tar_gz(self):
        p = os.path.join(self.d, "archive.tar.gz")
        with tarfile.open(p, "w:gz") as t:
            data = b"hello"
            info = tarfile.TarInfo(name="file.txt")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        result = far_gen.extract_tar(p)
        self.assertIn("file.txt", result)

    # --- RTF ---
    def test_rtf(self):
        p = self._file("doc.rtf", r"{\rtf1\ansi Hello World\par}")
        result = far_gen.extract_rtf(p)
        self.assertIn("Hello World", result)

    # --- Email ---
    def test_eml(self):
        eml = (
            "From: alice@example.com\r\n"
            "To: bob@example.com\r\n"
            "Subject: Test Email\r\n"
            "Date: Fri, 27 Feb 2026 10:00:00 +0000\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "Hello from FAR test."
        )
        p = self._file("test.eml", eml)
        result = far_gen.extract_eml(p)
        self.assertIn("alice@example.com", result)
        self.assertIn("Test Email", result)
        self.assertIn("Hello from FAR test", result)

    # --- Jupyter ---
    def test_ipynb(self):
        nb = {
            "cells": [
                {"cell_type": "markdown", "source": ["# My Notebook"]},
                {"cell_type": "code", "source": ["x = 42\nprint(x)"],
                 "outputs": [{"output_type": "stream", "text": ["42\n"]}]},
            ]
        }
        p = self._file("notebook.ipynb", json.dumps(nb))
        result = far_gen.extract_ipynb(p)
        self.assertIn("My Notebook", result)
        self.assertIn("x = 42", result)
        self.assertIn("42", result)

    # --- farignore glob ---
    def test_farignore_glob(self):
        with open(os.path.join(self.d, ".farignore"), "w") as f:
            f.write("*.tmp\nsecrets/\nbuild/**\n")
        patterns = far_gen.load_farignore(self.d)
        self.assertTrue(far_gen.should_ignore(os.path.join(self.d, "file.tmp"), self.d, patterns))
        self.assertTrue(far_gen.should_ignore(os.path.join(self.d, "secrets", "key.pem"), self.d, patterns))
        self.assertTrue(far_gen.should_ignore(os.path.join(self.d, "build", "out", "app.js"), self.d, patterns))
        self.assertFalse(far_gen.should_ignore(os.path.join(self.d, "README.md"), self.d, patterns))

    # --- layout frontmatter ---
    def test_meta_has_pipeline_and_deterministic(self):
        p = self._file("note.txt", "test content")
        meta_path = far_gen.generate_file_meta(p, self.d, [])
        with open(meta_path) as f:
            content = f.read()
        self.assertIn("pipeline:", content)
        self.assertIn("deterministic: true", content)
        self.assertIn("sha256:", content)

    # --- pipeline stale detection ---
    def test_pipeline_change_triggers_reextract(self):
        p = self._file("note.txt", "hello")
        meta_path = far_gen.generate_file_meta(p, self.d, [])
        # Tamper pipeline version in meta
        with open(meta_path, "r") as f:
            content = f.read()
        with open(meta_path, "w") as f:
            f.write(content.replace(far_gen.PIPELINE_ID, "far_gen_v0"))
        import time; time.sleep(0.05)
        # Should re-extract because pipeline changed
        far_gen.generate_file_meta(p, self.d, [])
        with open(meta_path) as f:
            new_content = f.read()
        self.assertIn(far_gen.PIPELINE_ID, new_content)


if __name__ == "__main__":
    unittest.main()

    # --- Video Processing ---
    def test_video_metadata(self):
        # Create a tiny 1-second dummy video using ffmpeg
        p = os.path.join(self.d, "dummy.mp4")
        import subprocess
        try:
            subprocess.run([
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=1', p
            ], capture_output=True, check=True)
        except Exception:
            self.skipTest("ffmpeg not available to create test video")

        # Test base extraction (metadata only, no OCR by default if mode A finds no text)
        os.environ["FAR_VIDEO_MODE"] = "A"
        result = far_gen.extract_media_metadata(p, "video/mp4")
        self.assertIn("Media Info (ffprobe)", result)
        self.assertIn("duration", result)
