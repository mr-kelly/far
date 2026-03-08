#!/bin/bash
# Run FAR tests

cd "$(dirname "$0")"

echo "🧪 Running FAR Tests..."
echo ""

# Run tests
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  PYTHON_BIN=python3
fi

"$PYTHON_BIN" -m unittest discover -s . -p "test_*.py" -v

echo ""
echo "✅ Tests completed"
