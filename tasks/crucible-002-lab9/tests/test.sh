#!/bin/bash
# Writes one number in [0, 1] to /logs/verifier/reward.txt.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /tests && python3 grade.py
