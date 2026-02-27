#!/bin/bash
# Run FAR tests

cd "$(dirname "$0")"

echo "🧪 Running FAR Tests..."
echo ""

# Run tests
python -m unittest discover -s . -p "test_*.py" -v

echo ""
echo "✅ Tests completed"
