#!/bin/bash
set -euo pipefail

# Check if a project directory is ready for building
# Usage: check-project.sh <project_directory>

PROJECT_DIR=$1

if [ -z "$PROJECT_DIR" ]; then
    echo "Usage: check-project.sh <project_directory>"
    exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Project directory $PROJECT_DIR does not exist"
    exit 1
fi

# Check for essential files
ESSENTIAL_FILES=("Makefile" "README.md")

for file in "${ESSENTIAL_FILES[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        echo "Missing $file in $PROJECT_DIR"
        exit 1
    fi
done

echo "All essential files are present in $PROJECT_DIR."
