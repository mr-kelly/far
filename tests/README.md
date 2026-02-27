# FAR Tests

Test suite for File-Augmented Retrieval.

## Structure

- `test_far.py` - Core functionality tests (file processing, ignore patterns, directory metadata)
- `test_cache.py` - Caching mechanism tests (mtime, content hash)
- `fixtures/` - Sample files for testing (markdown, JSON, Python, images, etc.)

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_far.py

# Run with unittest
python -m unittest discover tests/

# Run single test
python tests/test_far.py
```

## Fixtures

The `fixtures/` directory contains sample files for testing:

- `sample.md` - Markdown document
- `sample.json` - JSON data
- `sample.py` - Python script
- `sample.png` - Test image (if ImageMagick available)
- `sample.txt` - Plain text fallback

## Requirements

Tests use only Python standard library. Optional dependencies for full testing:

- `pytest` - Better test runner
- ImageMagick - For image fixture generation
