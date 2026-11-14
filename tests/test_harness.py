# Copyright 2026 Robina Mirbahar
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Verification and unit test suite for ple-veriflow-harness.

Validates:
1. `harness.py` provider routing, streaming prompt-cache warming (`SETTINGS`),
   capability profiles (`MODEL_SPECS`) across all 8 sponsored `google-cloud/*`
   models and local BYO `gemini-4-carbon`, reasoning effort, and token logging.
2. Live programmatic Gate-3 cold-read auditing (`snapshot_workdir`,
   `audit_deliverables`, and bounded Gate-3 remediation inside `solve()`)
   against corrupt `.zip`, `#REF!` `.xlsx`, incomplete `.ifc`/`.dxf`, broken
   `.py`, empty deliverables, and aborted `[tool call]` summaries.
3. Starter 29-task `artifacts/` integrity (mean reward `0.491242`, domain
   stratification, SHA-1 digests) and engineering checks on key deliverables.
4. Solo-author pronoun discipline (`I`/`my`, zero `we`/`our`/`ours`/`us`/`team`).
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
MANIFEST_PATH = ARTIFACTS_DIR / "manifest.json"

if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

import harness
import taskbridge

CIVIL_TASKS = {
    "data-center-site-model",
    "emergency-spillway-check",
    "engineers-estimate-check",
    "fill-compaction-acceptance",
    "footing-settlement-verification",
    "foundation-strategy",
    "frame-extension-method",
    "landscape-sheet-revision",
    "shoring-design-verification",
}
ELECTRICAL_TASKS = {
    "backfeed-energization-reply",
    "data-hall-device-takeoff",
    "division-26-specifications",
    "lv-cable-sizing",
    "mv-conveyance-study",
    "permission-to-operate-memo",
    "pre-application-capacity-response",
    "solar-supplemental-review",
    "solar-witness-test-package",
}
MECHANICAL_TASKS = {
    "cooling-water-flush-plan",
    "data-hall-mep-routing",
    "data-hall-mep-routing-offset",
    "fire-solve-convergence",
    "fire-test-validation-memo",
    "heat-rejection-life-cycle-cost",
    "les-mesh-resolution",
}
STRUCTURAL_TASKS = {
    "eor-review-corrections",
    "roof-deck-design",
    "seismic-diaphragm-shear",
    "wind-diaphragm-shear",
}
EXPECTED_SPONSORED = {
    "claude-opus-5-5",
    "gemini-4-argon",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
    "gpt-oss-120b",
    "glm-5.2",
    "gemma-4-26b",
    "llama-4-maverick",
}


def git_blob_sha1(path: pathlib.Path) -> str:
  """Computes Git SHA-1 blob digest (`blob <size>\\0<bytes>`) of a file."""
  data = path.read_bytes()
  header = f"blob {len(data)}\x00".encode("ascii")
  return hashlib.sha1(header + data).hexdigest()


class SessionStub:
  """Minimal session double recording logs, usage, and running container Python."""

  def __init__(
      self,
      workdir: str = "/workspace",
      remaining_sec: float | None = 3600.0,
  ) -> None:
    self.workdir = workdir
    self.instruction = "Deliver validated engineering outputs in submission.zip."
    self.mcp_servers = [{"name": "bim_server"}]
    self.final_message = ""
    self.logs: list[str] = []
    self.usages: list[dict[str, int | str]] = []
    self._remaining = remaining_sec

  def time_left(self) -> float | None:
    return self._remaining

  async def exec(self, command: str, timeout_sec: int = 120) -> dict[str, object]:
    """Executes the embedded container Python script with `sys.executable`."""
    del timeout_sec
    match = re.search(
        r"""base64\.b64decode\(["']([A-Za-z0-9+/=]+)["']\)""", command
    )
    json_match = re.search(
        r"<<'__PE_VERIFLOW_JSON__'\n(.*?)\n__PE_VERIFLOW_JSON__",
        command,
        re.DOTALL,
    )
    if not match or not json_match:
      return {"exit_code": 1, "output": "unrecognized test exec command"}
    code = harness.base64.b64decode(match.group(1)).decode("utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json_match.group(1),
        capture_output=True,
        text=True,
        check=False,
    )
    return {"exit_code": proc.returncode, "output": proc.stdout}

  async def log(self, text: str) -> None:
    self.logs.append(text)

  async def usage(
      self,
      model: str,
      input_tokens: int = 0,
      output_tokens: int = 0,
      cache_read_tokens: int = 0,
  ) -> None:
    self.usages.append({
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
    })


class RelayStub:
  """Relay double providing localhost MCP URL formatting."""

  def mcp_url(self, name: str) -> str:
    return f"http://127.0.0.1:41920/mcp/{name}"


class TestHarnessVerification(unittest.TestCase):
  """Unit and deliverable verification suite for `ple-veriflow-harness`."""

  @classmethod
  def setUpClass(cls) -> None:
    cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

  def test_01_prompt_and_deadline_settings(self) -> None:
    """Checks 3-Gate prompt text, TIME_NOTE formatting, and streaming cache settings."""
    self.assertEqual(harness.STOP_BEFORE_SEC, 90)
    self.assertEqual(harness.WORK_RESERVE_SEC, 240)
    self.assertEqual(harness.SETTINGS["cacheWarming"], "streaming")
    self.assertEqual(harness.SETTINGS["retry"]["maxRetries"], 8)
    self.assertEqual(harness.SETTINGS["httpIdleTimeoutMs"], 3_600_000)

    session = SessionStub(workdir="/app/files", remaining_sec=5400.0)
    rendered = harness.note(session)
    self.assertIn("Gate 1 (Authority & Revision Reconciliation)", rendered)
    self.assertIn("Gate 2 (Programmatic Calculation & Dimensional Audit)", rendered)
    self.assertIn("Gate 3 (Independent Cold-Read Deliverable Check)", rendered)
    self.assertIn("/app/files", rendered)
    self.assertIn("90 minutes", rendered)

  def test_02_provider_routing_and_config(self) -> None:
    """Tests `provider()` and `configure()` across Claude, Gemini, and OpenAI."""
    old_env = os.environ.copy()
    try:
      os.environ.clear()
      os.environ["ANTHROPIC_BASE_URL"] = "http://host.docker.internal:4000/anthropic"
      os.environ["MODEL_NAME"] = "claude-opus-5-5"
      name, cfg = harness.provider()
      self.assertEqual(name, "anthropic")
      self.assertEqual(cfg["api"], "anthropic-messages")
      self.assertEqual(cfg["compat"], harness.COMPAT)
      self.assertFalse(cfg["compat"]["supportsStrictTools"])

      os.environ.clear()
      os.environ["GOOGLE_GEMINI_BASE_URL"] = "http://host.docker.internal:4000/gemini"
      os.environ["MODEL_NAME"] = "gemini-4-argon"
      name_g, cfg_g = harness.provider()
      self.assertEqual(name_g, "google")
      self.assertTrue(cfg_g["baseUrl"].endswith("/v1beta"))
      self.assertEqual(cfg_g["api"], "google-generative-ai")

      os.environ.clear()
      os.environ["MODEL_BASE_URL"] = "http://host.docker.internal:4000/v1"
      os.environ["MODEL_NAME"] = "gpt-oss-120b"
      with tempfile.TemporaryDirectory() as tmp:
        agent_dir = pathlib.Path(tmp)
        session = SessionStub()
        relay = RelayStub()
        with mock.patch.object(harness, "in_catalog", return_value=False):
          prov_name, mod_name = harness.configure(agent_dir, relay, session, {})
        self.assertEqual(prov_name, "model")
        self.assertEqual(mod_name, "gpt-oss-120b")
        models_cfg = json.loads((agent_dir / "models.json").read_text(encoding="utf-8"))
        self.assertEqual(models_cfg["providers"]["model"]["models"][0]["contextWindow"], 131072)
        settings = json.loads((agent_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["cacheWarming"], "streaming")
        self.assertEqual(settings["retry"]["maxRetries"], 8)
        mcp_cfg = json.loads((agent_dir / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(
            mcp_cfg["mcpServers"]["bim_server"]["url"],
            "http://127.0.0.1:41920/mcp/bim_server",
        )
    finally:
      os.environ.clear()
      os.environ.update(old_env)

  def test_03_all_sponsored_models_and_thinking(self) -> None:
    """Verifies explicit capabilities for all 8 sponsored models plus gemini-4-carbon."""
    for model_id in EXPECTED_SPONSORED | {"gemini-4-carbon"}:
      spec = harness.model_limits(model_id)
      self.assertGreaterEqual(spec["contextWindow"], 131072)
      self.assertGreaterEqual(spec["maxTokens"], 32000)
      self.assertNotIn("reasoning", spec)
    self.assertEqual(harness.thinking_level("anthropic", "claude-opus-5-5"), "max")
    self.assertEqual(harness.thinking_level("model", "glm-5.2"), "max")
    self.assertEqual(harness.thinking_level("google", "gemini-4-argon"), "high")
    self.assertEqual(harness.thinking_level("google", "gemini-4-carbon"), "high")

  def test_04_token_and_cache_accounting(self) -> None:
    """Tests `harness.Run.on_line` token and prompt-cache accounting."""
    session = SessionStub()
    runner = harness.Run(session, "claude-opus-5-5")
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "stopReason": "end_turn",
            "content": [{"type": "text", "text": "Gate 3 verification passed: 0 defects."}],
            "usage": {"input": 12000, "cacheRead": 148000, "cacheWrite": 4000, "output": 1850},
        },
    }
    asyncio.run(runner.on_line(json.dumps(event).encode("utf-8")))
    self.assertEqual(runner.replies, 1)
    self.assertEqual(session.final_message, "Gate 3 verification passed: 0 defects.")
    self.assertEqual(session.usages[0]["input_tokens"], 164000)
    self.assertEqual(session.usages[0]["cache_read_tokens"], 148000)

  def test_05_programmatic_gate3_audit_and_remediation(self) -> None:
    """Tests live cold-read detection across corrupt ZIP/XLSX/IFC/DXF and remediation."""
    with tempfile.TemporaryDirectory() as tmp:
      work = pathlib.Path(tmp)
      (work / "existing.txt").write_text("input", encoding="utf-8")
      session = SessionStub(workdir=str(work), remaining_sec=1800.0)
      with mock.patch.object(
          harness, "_audit_roots", return_value=[str(work)]
      ):
        baseline = asyncio.run(harness.snapshot_workdir(session))
        self.assertEqual(len(baseline), 1)

        # Case 1: Aborted `[tool call]` with zero outputs is caught
        session.final_message = "[tool call]"
        defects_empty = asyncio.run(harness.audit_deliverables(session, baseline))
        self.assertTrue(any("[tool call]" in d for d in defects_empty))

        # Case 2: Corrupt ZIP, truncated IFC, and Excel `#REF!` inside ZIP are caught
        bad_zip = work / "submission.zip"
        bad_xlsx = io.BytesIO()
        with zipfile.ZipFile(bad_xlsx, "w") as xz:
          xz.writestr("xl/workbook.xml", "<workbook/>")
          xz.writestr("xl/worksheets/sheet1.xml", '<worksheet><sheetData><row><c t="e"><v>#REF!</v></c></row></sheetData></worksheet>')
        with zipfile.ZipFile(bad_zip, "w") as zf:
          zf.writestr("calc_book.xlsx", bad_xlsx.getvalue())
          zf.writestr("bad.json", "{not-json")
        (work / "model.ifc").write_text("ISO-10303-21;\nIFCPROJECT();\n", encoding="utf-8")
        session.final_message = "Delivered submission.zip and model.ifc."
        defects_bad = asyncio.run(harness.audit_deliverables(session, baseline))
        self.assertTrue(any("Excel error cell" in d for d in defects_bad))
        self.assertTrue(any("invalid JSON" in d for d in defects_bad))
        self.assertTrue(any("incomplete IFC" in d for d in defects_bad))

        # Case 3: Clean files pass with 0 defects
        (work / "model.ifc").write_text(
            "ISO-10303-21;\nIFCPROJECT();\nEND-ISO-10303-21;\n",
            encoding="utf-8",
        )
        good_xlsx = io.BytesIO()
        with zipfile.ZipFile(good_xlsx, "w") as xz:
          xz.writestr("xl/workbook.xml", "<workbook/>")
          xz.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData/></worksheet>")
        with zipfile.ZipFile(bad_zip, "w") as zf:
          zf.writestr("calc_book.xlsx", good_xlsx.getvalue())
          zf.writestr("ok.json", '{"status": "ok"}')
          zf.writestr("plan.dxf", "0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
        defects_good = asyncio.run(harness.audit_deliverables(session, baseline))
        self.assertEqual(defects_good, [])

        # Case 4: `solve()` invokes one bounded remediation pass when defects exist
        calls: list[bytes] = []

        async def fake_pass(sess, prompt_bytes, *, stop_before_sec):
          calls.append(prompt_bytes)
          run = harness.Run(sess, "claude-opus-5-5")
          run.replies = 1
          if len(calls) == 1:
            sess.final_message = "[tool call]"
          else:
            (work / "output.json").write_text('{"fixed": true}', encoding="utf-8")
            sess.final_message = "Fixed deliverables and verified on disk."
          return run, taskbridge.Finished(0, "", False)

        with mock.patch.object(harness, "_run_pi_pass", side_effect=fake_pass):
          out = asyncio.run(harness.solve(session))
        self.assertEqual(len(calls), 2)
        self.assertIn(b"Gate-3 Cold-Read Deliverable Defects Detected", calls[1])
        self.assertIn("Fixed deliverables", out)

  def test_06_starter_manifest_provenance_and_real_domains(self) -> None:
    """Verifies all 29 starter dev tasks, exact domain groupings, and SHA-1 digests."""
    tasks = self.manifest["tasks"]
    self.assertEqual(len(tasks), 29)
    all_sets = CIVIL_TASKS | ELECTRICAL_TASKS | MECHANICAL_TASKS | STRUCTURAL_TASKS
    self.assertEqual(set(tasks.keys()), all_sets)
    self.assertEqual(len(CIVIL_TASKS), 9)
    self.assertEqual(len(ELECTRICAL_TASKS), 9)
    self.assertEqual(len(MECHANICAL_TASKS), 7)
    self.assertEqual(len(STRUCTURAL_TASKS), 4)

    overall = sum(float(t["reward"]) for t in tasks.values()) / 29
    civ = sum(float(tasks[k]["reward"]) for k in CIVIL_TASKS) / 9
    elec = sum(float(tasks[k]["reward"]) for k in ELECTRICAL_TASKS) / 9
    mech = sum(float(tasks[k]["reward"]) for k in MECHANICAL_TASKS) / 7
    stru = sum(float(tasks[k]["reward"]) for k in STRUCTURAL_TASKS) / 4
    self.assertAlmostEqual(overall, 0.491242, places=5)
    self.assertAlmostEqual(civ, 0.617013, places=4)
    self.assertAlmostEqual(elec, 0.482183, places=4)
    self.assertAlmostEqual(mech, 0.447678, places=4)
    self.assertAlmostEqual(stru, 0.304878, places=4)

    for task_id, meta in tasks.items():
      task_dir = ARTIFACTS_DIR / task_id
      self.assertTrue(task_dir.is_dir(), f"Missing task directory: {task_id}")
      for rel_path, expected_sha in (meta.get("files") or {}).items():
        disk_path = task_dir / "files" / rel_path
        self.assertTrue(disk_path.is_file(), f"Missing deliverable on disk: {disk_path}")
        self.assertEqual(git_blob_sha1(disk_path), expected_sha)

  def test_07_key_engineering_deliverables(self) -> None:
    """Checks `lv-cable-sizing`, `seismic-diaphragm-shear`, `data-center-site-model`, and `footing-settlement`."""
    lv_zip = (
        ARTIFACTS_DIR
        / "lv-cable-sizing"
        / "files"
        / "filesystem"
        / "electrical__lv_cable_sizing__blind"
        / "output"
        / "submission.zip"
    )
    with zipfile.ZipFile(lv_zip) as zf:
      rows = list(csv.DictReader(io.StringIO(zf.read("wire_schedule.csv").decode("utf-8"))))
      self.assertEqual(len(rows), 32)
      by_id = {r["circuit"]: r for r in rows}
      self.assertEqual(by_id["SE-1"]["duct_ids"], "D1, D2, D5, D6, D9, D10")
      self.assertAlmostEqual(float(by_id["B-17"]["cumulative_vd_pct"]), 4.928, places=3)

    ifc_path = (
        ARTIFACTS_DIR
        / "data-center-site-model"
        / "files"
        / "app"
        / "files"
        / "frontier__DCBim__p6_002"
        / "submission"
        / "model.ifc"
    )
    ifc_text = ifc_path.read_text(encoding="utf-8")
    self.assertIn("FILE_SCHEMA(('IFC4'));", ifc_text)
    self.assertIn("END-ISO-10303-21;", ifc_text)

    docx_path = (
        ARTIFACTS_DIR
        / "footing-settlement-verification"
        / "files"
        / "filesystem"
        / "Thelbridge_Verification_Memo_Item051_BlockC.docx"
    )
    with zipfile.ZipFile(docx_path) as zf:
      xml_text = zf.read("word/document.xml").decode("utf-8")
      self.assertIn("746.0", xml_text)
      self.assertIn("CB-GEO-007", xml_text)

  def test_08_solo_author_and_context_limits(self) -> None:
    """Ensures `task-tools.ts`, `harness.py`, and `README.md` respect rules and solo pronouns."""
    ts_code = (REPO_ROOT / "task-tools.ts").read_text(encoding="utf-8")
    self.assertIn("over 100 KB, so its middle was cut", ts_code)
    self.assertIn("MAX_EXEC_SEC = 600", ts_code)
    self.assertIn("TASK_RELAY_URL", ts_code)

    tb_code = (REPO_ROOT / "taskbridge.py").read_text(encoding="utf-8")
    self.assertIn("stop_before_sec", tb_code)
    self.assertIn("final_message", tb_code)

    harness_text = (REPO_ROOT / "harness.py").read_text(encoding="utf-8")
    self.assertIsNone(re.search(r"\b(we|our|ours|us|team)\b", harness_text, re.I))

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    self.assertIsNone(re.search(r"\b(we|our|ours|us|team)\b", readme_text, re.I))


if __name__ == "__main__":
  unittest.main(verbosity=2)
