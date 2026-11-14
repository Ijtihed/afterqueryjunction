#!/bin/bash
# Human playtest server. Open http://localhost:8080 . Sessions are written to playtests/sessions/.
cd "$(dirname "$0")/../engine" && exec python3 -m crucible.server --play --web ../web --data ../playtests --port "${1:-8080}" --host 0.0.0.0
