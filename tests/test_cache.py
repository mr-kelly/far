import unittest
import os
import shutil
import tempfile
import sys
import time
from pathlib import Path

# Add the skill directory to path to import far_gen
skill_dir = Path(__file__).parent.parent / "skills" / "far"
sys.path.insert(0, str(skill_dir))
import far_gen

class TestFarGenCache(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.far_gen = far_gen
        
        # Override log function to avoid clutter
        self.far_gen.log = lambda msg, level="INFO": None
        
        # Override extractors to avoid expensive calls, we only test caching logic
        self.original_extract_pdf = self.far_gen.extract_pdf
        self.far_gen.extract_pdf = lambda f: "EXTRACTED_CONTENT"

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        self.far_gen.extract_pdf = self.original_extract_pdf

    def test_mtime_cache(self):
        """Test if processing is skipped when mtime/size match."""
        file_path = os.path.join(self.test_dir, "test.pdf")
        with open(file_path, "w") as f: f.write("dummy pdf content")
        
        # 1st Run: Should generate
        meta_path = self.far_gen.generate_file_meta(file_path, self.test_dir, [])
        self.assertTrue(os.path.exists(meta_path))
        
        # Capture modification time of .meta file
        meta_mtime_1 = os.path.getmtime(meta_path)
        
        # Sleep to ensure fs timestamp difference if modified
        time.sleep(0.1) 
        
        # 2nd Run (No changes): Should SKIP (meta mtime should NOT change)
        self.far_gen.generate_file_meta(file_path, self.test_dir, [])
        meta_mtime_2 = os.path.getmtime(meta_path)
        
        self.assertEqual(meta_mtime_1, meta_mtime_2, "Meta file should NOT be touched if source unchanged")

    def test_content_change_triggers_update(self):
        """Test if content change triggers regeneration."""
        file_path = os.path.join(self.test_dir, "test.pdf")
        with open(file_path, "w") as f: f.write("content v1")
        
        self.far_gen.generate_file_meta(file_path, self.test_dir, [])
        meta_mtime_1 = os.path.getmtime(file_path + ".meta")
        
        time.sleep(1.1) # Wait for FS mtime resolution
        
        # Modify file
        with open(file_path, "w") as f: f.write("content v2")
        
        # 3rd Run: Should UPDATE
        self.far_gen.generate_file_meta(file_path, self.test_dir, [])
        meta_mtime_2 = os.path.getmtime(file_path + ".meta")
        
        self.assertNotEqual(meta_mtime_1, meta_mtime_2, "Meta file SHOULD update when content changes")

if __name__ == '__main__':
    unittest.main()
