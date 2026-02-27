import unittest
import os
import shutil
import tempfile
import sys
from pathlib import Path

# Add the skill directory to path to import far_gen
skill_dir = Path(__file__).parent.parent / "skills" / "far"
sys.path.insert(0, str(skill_dir))
import far_gen

class TestFarGen(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.far_gen = far_gen

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_text_file_processing(self):
        """Test if a simple text file gets a .meta sidecar."""
        file_path = os.path.join(self.test_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("Hello FAR world")
        
        # Run generator
        meta_path = self.far_gen.generate_file_meta(file_path, self.test_dir, [])
        
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r") as f:
            content = f.read()
            self.assertIn("Hello FAR world", content)
            self.assertIn("pipeline:", content)

    def test_fixtures(self):
        """Test processing of fixture files."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        if not fixtures_dir.exists():
            self.skipTest("Fixtures directory not found")
        
        # Test markdown file
        md_file = fixtures_dir / "sample.md"
        if md_file.exists():
            meta_path = self.far_gen.generate_file_meta(str(md_file), str(fixtures_dir), [])
            self.assertTrue(os.path.exists(meta_path))
            with open(meta_path, "r") as f:
                content = f.read()
                self.assertIn("Sample Document", content)
        
        # Test JSON file
        json_file = fixtures_dir / "sample.json"
        if json_file.exists():
            meta_path = self.far_gen.generate_file_meta(str(json_file), str(fixtures_dir), [])
            self.assertTrue(os.path.exists(meta_path))
            with open(meta_path, "r") as f:
                content = f.read()
                self.assertIn("FAR Test Data", content)
        
        # Test Python file
        py_file = fixtures_dir / "sample.py"
        if py_file.exists():
            meta_path = self.far_gen.generate_file_meta(str(py_file), str(fixtures_dir), [])
            self.assertTrue(os.path.exists(meta_path))
            with open(meta_path, "r") as f:
                content = f.read()
                self.assertIn("greet", content)

    def test_ignore_pattern(self):
        """Test if files matching .farignore are skipped."""
        # Create .farignore
        with open(os.path.join(self.test_dir, ".farignore"), "w") as f:
            f.write("secret.txt\nignored_dir/")
            
        # Create ignored file
        secret_path = os.path.join(self.test_dir, "secret.txt")
        with open(secret_path, "w") as f:
            f.write("This should be ignored")

        # Load patterns
        patterns = self.far_gen.load_farignore(self.test_dir)
        
        # Run check
        meta_path = self.far_gen.generate_file_meta(secret_path, self.test_dir, patterns)
        self.assertIsNone(meta_path)
        self.assertFalse(os.path.exists(secret_path + ".meta"))

    def test_dir_meta_generation(self):
        """Test if .dir.meta aggregates file info."""
        # Create 2 files
        f1 = os.path.join(self.test_dir, "a.txt")
        f2 = os.path.join(self.test_dir, "b.txt")
        with open(f1, "w") as f: f.write("Content A")
        with open(f2, "w") as f: f.write("Content B")
        
        # Process files manually first (simulating main loop)
        m1 = self.far_gen.generate_file_meta(f1, self.test_dir, [])
        m2 = self.far_gen.generate_file_meta(f2, self.test_dir, [])
        
        files_in_dir = [("a.txt", m1), ("b.txt", m2)]
        
        self.far_gen.generate_dir_meta(self.test_dir, self.test_dir, [], files_in_dir)
        
        dir_meta = os.path.join(self.test_dir, ".dir.meta")
        self.assertTrue(os.path.exists(dir_meta))
        
        with open(dir_meta, "r") as f:
            content = f.read()
            self.assertIn("Content A", content)
            self.assertIn("Content B", content)
            self.assertIn("type: directory", content)

if __name__ == '__main__':
    unittest.main()
