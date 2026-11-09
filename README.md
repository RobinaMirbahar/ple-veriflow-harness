# PE-VeriFlow: 3-Gate Verification Agent Harness for Physical-Engineering's Last Exam (PLE)

An open-source autonomous engineering agent harness (`ple-veriflow-harness`) built on the [Pi coding agent](https://github.com/badlogic/pi-mono) (`@earendil-works/pi-coding-agent` v1.1.0) paired with `google-cloud/claude-opus-5-5` for the **Google — Agent Harness on Physical-Engineering's Last Exam (PLE)** competition.

## Overview

Physical engineering deliverables fail not from single-formula syntax errors, but from **silent cross-document contradictions**, **superseded drawing revisions**, **unit/datum mismatches**, and **unverified deliverable packaging**. `ple-veriflow-harness` wraps a container-isolated tool relay (`taskbridge.Relay`) with a **3-Gate Physical-Engineering Verification Protocol (PE-VeriFlow)**:

1. **Gate 1 — Authority & Revision Reconciliation:** Cross-checks project drawings, specifications, geotechnical borings, and RFIs/addenda before computing, explicitly filtering out superseded revisions (e.g., rejecting `EDS-26 Rev 2` in favor of `Rev 4`, or flagging unsealed consolidation sheets in `CB-GEO-007`).
2. **Gate 2 — Programmatic Calculation & Dimensional Audit:** Enforces code-based calculation in Python (`ifcopenshell`, `numpy`, `scipy`, `openpyxl`, `ezdxf`, `python-docx`) with explicit unit-conversion and boundary checks.
3. **Gate 3 — Independent Cold-Read Deliverable Verification:** Writes a clean verification script that re-opens every generated deliverable from disk (`submission.zip`, `.ifc`, `.xlsx`, `.dxf`, `.docx`, `.csv`) and validates schema completeness, row counts, and governing margins prior to emitting `done`.

## Repository Structure

| File | Purpose |
|---|---|
| `submission.yaml` | Configures `name: ple-veriflow-harness`, `model_api: google-cloud/claude-opus-5-5`, `install`, and `serve` |
| `serve.py` | WebSocket server entrypoint listening on `0.0.0.0:$PORT` and dispatching tasks to `harness.solve` |
| `harness.py` | Configures headless Pi sessions, model provider routing (`anthropic`, `google`, `openai-completions`), MCP server proxying, and the 3-Gate PE-VeriFlow system prompt |
| `task-tools.ts` | TypeScript extension routing `read`, `write`, `edit`, and `bash` tool calls over HTTP to `taskbridge.Relay` inside the task container |
| `taskbridge.py` | PLE competition WebSocket protocol implementation, process lifecycle manager, and local HTTP relay |
| `package.json`, `package-lock.json` | Pinned `@earendil-works/pi-coding-agent` (`1.1.0`) dependencies |
| `artifacts/` | Unpacked dev-set outputs and `manifest.json` across all 29 public PLE dev tasks |
| `figures/` | Architecture, Score-vs-Cost Pareto, and Dev-Set Failure Taxonomy figures for the Kaggle Writeup |
| `LICENSE` | Apache-2.0 License |

## Verification & Evaluation

From the official [PLE Competition Kit](https://github.com/google-research/ple) checkout alongside this repository:

```bash
uv run python -m kit check ../ple-veriflow-harness
uv run python -m kit artifacts ../ple-veriflow-harness
uv run python eval/run.py ../ple-veriflow-harness
```
