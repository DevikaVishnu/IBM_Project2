#!/usr/bin/env bash
# Fetch the IBM AssetOpsBench dataset from HuggingFace into this directory.
#   Patel et al. (2025), "AssetOpsBench: Benchmarking AI Agents for Task
#   Automation in Industrial Asset Operations and Maintenance" arXiv:2506.03828
#   https://huggingface.co/datasets/ibm-research/AssetOpsBench
#   Framework / agent code: https://github.com/IBM/AssetOpsBench
set -euo pipefail
cd "$(dirname "$0")"

BASE="https://huggingface.co/datasets/ibm-research/AssetOpsBench/resolve/main"

FILES=(
  README.md
  data/scenarios/all_utterance.jsonl
  data/asset/compressor_utterance.jsonl
  data/asset/hydrolicpump_utterance.jsonl
  data/task/rule_monitoring_scenarios.jsonl
  data/task/failure_mapping_senarios.jsonl
  data/task/phm_utterance.jsonl
  data/failuresensoriq_standard/all.jsonl
  data/failuresensoriq_standard/all_10_options.jsonl
  data/failuresensoriq_standard/all_multi_answers.jsonl
  data/failuresensoriq_standard/sample_50_questions.jsonl
  data/failuresensoriq_perturbed/all_10_options_all_perturbed_simple.jsonl
  data/failuresensoriq_perturbed/all_10_options_perturbed_complex.jsonl
)

for f in "${FILES[@]}"; do
  out="${f#data/}"
  mkdir -p "$(dirname "$out")"
  echo "Fetching $f ..."
  curl -fsSL -o "$out" "$BASE/$f"
done

find . -name '*.jsonl' -exec wc -l {} +
