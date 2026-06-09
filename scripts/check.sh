#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

bash -n install-and-run-majestic-proton.sh
python3 -m compileall -q majestic_linux tests
python3 -m unittest discover -s tests
