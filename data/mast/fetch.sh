#!/usr/bin/env bash
# Fetch the MAST annotated dataset (MAD) from HuggingFace into this directory.
#   Cemri et al. (2025), "Why Do Multi-Agent LLM Systems Fail?" arXiv:2503.13657v2
#   https://huggingface.co/datasets/mcemri/MAD
set -euo pipefail
cd "$(dirname "$0")"

BASE="https://huggingface.co/datasets/mcemri/MAD/resolve/main"

for f in MAD_human_labelled_dataset.json MAD_full_dataset.json; do
  echo "Fetching $f ..."
  curl -fL --progress-bar -o "$f" "$BASE/$f"
done

ls -lh MAD_*.json
