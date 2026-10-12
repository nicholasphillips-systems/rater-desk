#!/bin/bash
# Run Rater Desk
set -e
cd "$(dirname "$0")"
source ~/.venvs/rater-desk/bin/activate
exec python main.py "$@"
