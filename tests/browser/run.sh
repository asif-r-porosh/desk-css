#!/bin/sh
# Create a private virtual environment on first use, then run the check.
# Usage: tests/browser/run.sh firefox safari
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi
exec .venv/bin/python check.py "$@"
