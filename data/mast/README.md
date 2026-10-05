# MAST dataset (MAD)

Annotated multi-agent system traces from **MAST — Multi-Agent System Failure Taxonomy**:

> Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2
> Dataset: https://huggingface.co/datasets/mcemri/MAD · Code: https://github.com/multi-agent-systems-failure-taxonomy/MAST

The JSON files are **not tracked in git** (190 MB combined). Re-fetch them with:

```bash
./data/mast/fetch.sh
```

## Files

| File | Size | Records | Annotation source |
|---|---|---|---|
| `MAD_full_dataset.json` | 190 MB | 1642 | LLM-as-a-judge |
| `MAD_human_labelled_dataset.json` | 2.5 MB | 19 | Human annotators |

## Record shape

`MAD_full_dataset.json` — same shape as the traces already in `tests/`, so records drop
straight into `tests/process_trace.py`:

```jsonc
{
  "mas_name": "ChatDev",          // AG2 | ChatDev | MetaGPT | Magentic | OpenManus | AppWorld | HyperAgent
  "llm_name": "GPT-4o",
  "benchmark_name": "ProgramDev",
  "trace_id": 8,
  "trace": { "key": "...", "index": 8, "trajectory": "...raw log text..." },
  "mast_annotation": { "1.1": 0, "1.3": 1, ... }   // 14 failure-mode codes, 0/1
}
```

`MAD_human_labelled_dataset.json` uses `round` + `annotations` in place of
`llm_name` + `mast_annotation`.

## Coverage (`MAD_full_dataset.json`)

| MAS | Benchmark | Traces |
|---|---|---|
| MetaGPT | ProgramDev | 230 |
| AG2 | GSM | 223 |
| AG2 | Olympiad | 206 |
| ChatDev | ProgramDev-v2 | 200 |
| MetaGPT | ProgramDev-v2 | 200 |
| Magentic | GAIA | 195 |
| AG2 | MMLU | 168 |
| ChatDev | ProgramDev | 130 |
| OpenManus | ProgramDev | 30 |
| AppWorld | Test-C | 30 |
| HyperAgent | SWE-Bench-Lite | 30 |

## Extracting a single trace

```bash
python3 -c "
import json
d = json.load(open('data/mast/MAD_full_dataset.json'))
r = next(x for x in d if x['mas_name']=='ChatDev' and x['trace_id']==8)
json.dump(r, open('raw_trace.json','w'), indent=2)
"
python tests/process_trace.py raw_trace.json processed.json
python tests/belief_extractor.py processed.json enriched.json
```

The 14 MAST failure-mode codes are mirrored in `MAST_REGISTRY` in `tests/process_trace.py`.
