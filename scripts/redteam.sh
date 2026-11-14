#!/bin/bash
# Runs a hostile script as the agent inside the real Harbor task and prints the
# reward the verifier assigns. Expected: 0.0000. See redteam/hostile_agent.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cp -r "$ROOT/tasks/${1:-crucible-001}" "$WORK/crucible-redteam"
cp "$ROOT/redteam/hostile_agent.sh" "$WORK/crucible-redteam/solution/solve.sh"
cd "$WORK" && harbor run -p ./crucible-redteam -a oracle -o "$WORK/jobs" >/dev/null 2>&1 || true
echo "reward: $(cat "$WORK"/jobs/*/crucible-redteam__*/verifier/reward.txt)"
tail -25 "$WORK"/jobs/*/crucible-redteam__*/agent/oracle.txt
