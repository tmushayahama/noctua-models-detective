#!/usr/bin/env bash
# Log only: barista log analysis without a git repo
#
# Steps: clean → filter → resolve ontology → resolve metadata → humanize → report
#
# Use this when you have a barista log file but no noctua-models repo clone.

LOG_FILE="logs/hold.log"
OUTPUT_DIR="downloads"
MODEL_ID="693b3c0900004140"

python -m src.pipeline \
    -f "$LOG_FILE" \
    -o "$OUTPUT_DIR" \
    -m "$MODEL_ID"
