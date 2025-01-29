#!/bin/bash
set -euo pipefail

# Validate JSON schemas
validate_schema() {
    local schema_file="$1"
    echo "Validating schema: $schema_file"

    if ! command -v jsonschema &> /dev/null; then
        echo "Error: jsonschema is not installed. Please install it via pip or add it to your project's dependencies."
        exit 1
    fi

    if ! jsonschema -i "$schema_file" "http://json-schema.org/draft-07/schema#"; then
        echo "Validation failed for schema: $schema_file"
        exit 1
    fi
}

# Find and validate all schema files
find core/schemas -name "*.schema.json" -type f | while read -r schema; do
    validate_schema "$schema"
done
