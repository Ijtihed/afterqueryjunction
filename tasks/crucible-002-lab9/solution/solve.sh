#!/bin/bash
# Reference run. Identifies the substances with three lab experiments through
# the public interface, then plans by exhaustive search (see solve.py).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
cp -r "$DIR"/. "$WORK"/
python3 "$WORK/solve.py"
