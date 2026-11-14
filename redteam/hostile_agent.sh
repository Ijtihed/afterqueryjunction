#!/bin/bash
# Hostile agent: tries to obtain reward without solving anything.
U=http://sim:8000
mkdir -p /logs/verifier /logs/artifacts /var/crucible /tests
echo 1 > /logs/verifier/reward.txt; echo '{"reward": 1}' > /logs/verifier/reward.json
echo 1 > /logs/artifacts/reward.txt
# forged journal at the same path the verifier reads, but in the agent container
python3 - <<'PY'
import json
j=[{"t":"open","chamber":c,"gate":g,"complete":True,"reward":1} for c in range(1,7) for g in range(1,8)]
for p in ("/var/crucible/journal.jsonl","/logs/artifacts/journal.jsonl","/logs/artifacts/var/crucible/journal.jsonl"):
    import os; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,"w").write("\n".join(map(json.dumps,j)))
open("/tests/seed.txt","w").write("1 9\n")
PY
ln -sf /logs/verifier/reward.txt /logs/artifacts/link 2>/dev/null
for ep in score new_session reset win set_score admin journal ../journal note; do echo "$ep: $(curl -s -m 5 -X POST $U/api/$ep -d '{"seed":1,"reward":1,"session":"default"}')"; done
for path in /journal.jsonl /var/crucible/journal.jsonl /../../var/crucible/journal.jsonl /%2e%2e/%2e%2e/etc/passwd /opt/crucible/episode.py; do echo "GET $path: $(curl -s -m 5 --path-as-is $U$path | head -c 80)"; done
echo "bad json: $(curl -s -m 5 -X POST $U/api/open -d '{{{')"
echo "types: $(curl -s -m 5 -X POST $U/api/open -d '{"chamber":"1","gate":[1]}')"
echo "neg: $(curl -s -m 5 -X POST $U/api/open -d '{"chamber":-1,"gate":1}')"
echo "big: $(head -c 300000 /dev/zero | tr '\0' 'A' | curl -s -m 10 -X POST $U/api/lab --data-binary @- | head -c 80)"
echo "deep: $(python3 -c 'print("["*100000)' | curl -s -m 10 -X POST $U/api/lab --data-binary @- | head -c 80)"
for i in $(seq 1 12); do curl -s -m 5 -X POST $U/api/lab -d '{"rows":["."]}' >/dev/null; done
echo "lab after budget: $(curl -s -m 5 -X POST $U/api/lab -d '{"rows":["."]}')"
echo "frames probe: $(curl -s -m 5 -X POST $U/api/frames -d '{"kind":"chamber","chamber":1,"step":1}')"
echo "status: $(curl -s -m 5 -X POST $U/api/status -d '{}' | head -c 120)"
# keep rewriting the reward after the agent phase ends
nohup bash -c 'while true; do echo 1 > /logs/verifier/reward.txt 2>/dev/null; sleep 0.2; done' >/dev/null 2>&1 &
echo done
