##!/bin/bash
# Full pipeline: barista log + noctua-models git repo
#
# Steps: clean → filter → resolve ontology → resolve metadata →
#        humanize → extract TTL versions → resolve TTL ontology → diff → report
#
# Prerequisites:
#   - A raw barista log file (e.g. from the Noctua server)
#   - A local clone of https://github.com/geneontology/noctua-models

LOG_FILE="logs/hold.log"
OUTPUT_DIR="downloads"
MODEL_ID="693b3c0900004140"
REPO_PATH="../noctua-models-temp"
AFTER="2026-02-01"

python -m src.pipeline \
    -f "$LOG_FILE" \
    -o "$OUTPUT_DIR" \
    -m "$MODEL_ID" \
    -r "$REPO_PATH" \
    --after "$AFTER"
