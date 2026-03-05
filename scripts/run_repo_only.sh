##!/bin/bash
# Repo only: TTL version diffs without a barista log
#
# Steps: resolve metadata → extract TTL versions → resolve TTL ontology → diff
#
# Use this when you have a noctua-models repo clone but no barista log file.
# Produces a human-readable changelog of model edits over time.

OUTPUT_DIR="downloads/reactome"
MODEL_ID="R-HSA-8964539"
REPO_PATH="../noctua-models-temp"
AFTER="2024-02-01"

python -m src.pipeline \
    -o "$OUTPUT_DIR" \
    -m "$MODEL_ID" \
    -r "$REPO_PATH" \
    --after "$AFTER"
