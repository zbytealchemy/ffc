#!/bin/bash
set -euo pipefail

# Check for required tools and their versions
check_tool() {
    local tool=$1
    local min_version=$2
    local version_cmd=$3

    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$tool not found"
        return 1
    fi

    if [ -n "$min_version" ]; then
        local current_version
        current_version=$($version_cmd)
        echo "$tool version: $current_version"
        if ! printf '%s\n%s\n' "$min_version" "$current_version" | sort -V -C; then
            echo "$tool version $current_version is less than required version $min_version"
            return 1
        fi
    fi
}

# Required tools and their minimum versions
REQUIRED_TOOLS=(
    "python:3.9:python --version 2>&1 | cut -d' ' -f2"
    "poetry:1.4.0:poetry --version 2>&1 | cut -d' ' -f3"
    "node:16.0.0:node --version 2>&1 | cut -c2-"
    "npm:8.0.0:npm --version"
    "git:2.0.0:git --version | cut -d' ' -f3"
    "docker:20.0.0:docker --version | cut -d' ' -f3 | cut -d'.' -f1-3"
)

echo "Checking required tools and versions..."
echo "======================================="

failed=0

for tool_spec in "${REQUIRED_TOOLS[@]}"; do
    IFS=':' read -r tool min_version version_cmd <<< "$tool_spec"
    if ! check_tool "$tool" "$min_version" "$version_cmd"; then
        failed=1
    fi
done

if [ $failed -eq 1 ]; then
    echo " Some required tools are missing or have incompatible versions"
    exit 1
else
    echo " All required tools are available with compatible versions"
    exit 0
fi

# Check versions across different runtimes
check_versions() {
    local version_file="$1"
    local expected_version

    # Get version from Python runtime
    expected_version=$(grep '^version = ' runtime/python/pyproject.toml | cut -d'"' -f2)

    # Check each runtime's version matches
    for runtime in runtime/*/; do
        if [ -f "${runtime}version.txt" ]; then
            local runtime_version
            runtime_version=$(cat "${runtime}version.txt")
            if [ "$runtime_version" != "$expected_version" ]; then
                echo "Version mismatch in ${runtime}: expected ${expected_version}, got ${runtime_version}"
                exit 1
            fi
        fi
    done
}

check_versions "runtime/python/pyproject.toml"
