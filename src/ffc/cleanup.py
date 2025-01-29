#!/usr/bin/env python3
import os
import shutil
from pathlib import Path


def cleanup_cache(directory):
    """Remove Python cache and pytest cache directories."""
    for root, dirs, _ in os.walk(directory):
        for d in dirs:
            if d == "__pycache__" or d == ".pytest_cache":
                path = Path(root) / d
                print(f"Removing {path}")
                try:
                    shutil.rmtree(path)
                except PermissionError:
                    print(f"Permission denied: {path}")
                except Exception as e:
                    print(f"Error removing {path}: {e}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    cleanup_cache(base_dir)
