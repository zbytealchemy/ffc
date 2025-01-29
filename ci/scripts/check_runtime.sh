#!/bin/bash
set -euo pipefail

# Check if a given runtime folder is ready to be built
# Usage: check_runtime.sh <runtime_folder>

RUNTIME_DIR=$1

if [ -z "$RUNTIME_DIR" ]; then
    echo "Usage: check_runtime.sh <runtime_folder>"
    exit 1
fi

if [ ! -d "$RUNTIME_DIR" ]; then
    echo "Runtime directory $RUNTIME_DIR does not exist"
    exit 1
fi

# Check for essential files
REQUIRED_FILES=(
    "pyproject.toml"
    "poetry.lock"
    "README.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$RUNTIME_DIR/$file" ]; then
        echo "Missing $file in $RUNTIME_DIR"
        exit 1
    fi
done

echo "All essential files are present in $RUNTIME_DIR."
