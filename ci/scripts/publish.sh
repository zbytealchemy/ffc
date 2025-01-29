#!/bin/bash
set -euo pipefail

# Publish packages to their respective registries
publish_python() {
    echo "Current directory: $(pwd)"
    echo "Attempting to publish from: src/ffc"
    if ! poetry publish --build; then
        echo "Failed to publish Python package"
        exit 1
    fi
}

# Main publish logic
main() {
    if [ $# -ne 1 ]; then
        echo "Usage: $0 VERSION"
        exit 1
    fi

    local version=$1
    cd src/ffc && poetry version "$version"
    publish_python

    # Tag the release
    git tag "v${version}"
    git push origin "v${version}"
}

if [ $# -ne 1 ]; then
    echo "Usage: $0 VERSION"
    exit 1
fi

main "$1"
