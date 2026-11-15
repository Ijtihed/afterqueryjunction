#!/bin/bash
# One command to check the submission end to end. Needs Docker, Harbor and python3.
#   1. unit and reward-integrity tests
#   2. exhaustive validation of the shipped seeds
#   3. trivial-policy baselines (same grading path as the verifier)
#   4. Harbor: reference run (expect 1.0) and do-nothing run (expect 0.0)
#   5. Harbor: hostile agent script (expect 0.0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TASK="${1:-crucible-001}"
echo "== 1/5 tests";      python3 -m unittest discover tests 2>&1 | tail -3
echo "== 2/5 validate";   python3 scripts/validate.py 1 2 3 | tail -1
echo "== 3/5 baselines";  python3 scripts/baselines.py 1 2 3
OUT="$(mktemp -d)"
reward() { cat "$OUT/$1"/*/"$TASK"__*/verifier/reward.txt; }
echo "== 4/5 harbor reference and do-nothing on $TASK"
(cd tasks && harbor run -p "./$TASK" -a oracle -o "$OUT/oracle" >/dev/null 2>&1) || true
(cd tasks && harbor run -p "./$TASK" -a nop -o "$OUT/nop" >/dev/null 2>&1) || true
echo "reference:  $(reward oracle)   (expect 1.0000)"
echo "do nothing: $(reward nop)   (expect 0.0000)"
echo "== 5/5 hostile agent"
scripts/redteam.sh "$TASK" | head -1
