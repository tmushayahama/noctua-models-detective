#!/usr/bin/env bash
# Repo only: TTL version diffs without a barista log
#
# Steps: resolve metadata → extract TTL versions → resolve TTL ontology → diff → changelog
#
# Use this when you have a noctua-models repo clone but no barista log file.
# Produces a human-readable changelog of model edits over time.

OUTPUT_DIR="downloads/val_analysis"
MODEL_ID="693b3c0900004140"
REPO_PATH="../noctua-models-temp"
AFTER="2026-02-01"

python -m src.pipeline \
    -o "$OUTPUT_DIR" \
    -m "$MODEL_ID" \
    -r "$REPO_PATH" \
    --after "$AFTER"
