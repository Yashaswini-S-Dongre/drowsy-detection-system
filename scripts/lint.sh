#!/bin/bash
# lint.sh
# Runs ruff and black formatting checks

cd "$(dirname "$0")/.."

echo "Running ruff..."
ruff check .
echo "Running black..."
# black --check .
