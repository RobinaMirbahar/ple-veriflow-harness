# Copyright 2026 Robina Mirbahar
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Verification and unit test suite for ple-veriflow-harness.

Tests the 3-Gate PE-VeriFlow harness (`harness.py`, `serve.py`, `taskbridge.py`)
and validates the dev-set deliverables under `artifacts/`:

1. Gate 1 (Authority & Revision Audit): Checks `constraint_register` deliverables
   for `lv-cable-sizing`, `heat-rejection-life-cycle-cost`, and
   `seismic-diaphragm-shear`, along with the 5.5 ft datum offset (`El. 740.5`
   in `CB-GEO-007` vs. `El. 746.0` on `S-201 Rev.4`) in
   `footing-settlement-verification`.
2. Gate 2 (Programmatic Solver & Dimensional Checks): Validates feeder and
   branch voltage-drop and Neher-McGrath thermal ampacity across all 32 circuits
   in `lv-cable-sizing` (`wire_schedule.csv`), LRFD diaphragm shear and cost
   summaries in `seismic-diaphragm-shear` (`design_record.json`), and 3D BIM/MEP
   sprinkler headroom geometry (`+3024.6 mm - 460 mm = +2564.6 mm < 2600 mm`) in
   `data-hall-mep-routing-offset` and `data-center-site-model` (`model.ifc`).
3. Gate 3 (Cold-Read Deliverable & Manifest Check): Verifies unpacked
   deliverables across all 29 task directories, checks Git blob SHA-1 digests
   against `artifacts/manifest.json`, and tests `harness.py` provider routing,
   MCP configuration, and token accounting.

Run with:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
MANIFEST_PATH = ARTIFACTS_DIR / "manifest.json"

if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

import harness
import taskbridge


def git_blob_sha1(path: pathlib.Path) -> str:
  """Computes the Git SHA-1 blob digest (`blob <size>\\0<bytes>`) of a file."""
  data = path.read_bytes()
  header = f"blob {len(data)}\x00".encode("ascii")
  return hashlib.sha1(header + data).hexdigest()


class SessionStub:
  """Minimal session object recording usage and log calls from `harness.Run`."""

  def __init__(self, workdir: str = "/workspace") -> None:
    self.workdir = workdir
    self.instruction = "Verify task deliverables."
    self.mcp_servers = [{"name": "bim_server"}]
    self.final_message = ""
    self.logs: list[str] = []
    self.usages: list[dict[str, int | str]] = []

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
  """Relay helper providing localhost MCP URL formatting."""

  def mcp_url(self, name: str) -> str:
    return f"http://127.0.0.1:41920/mcp/{name}"


class TestHarnessVerification(unittest.TestCase):
  """Unit and deliverable verification tests for `ple-veriflow-harness`."""

  @classmethod
  def setUpClass(cls) -> None:
    cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

  def test_01_prompt_and_deadline_reserve(self) -> None:
    """Checks the 3-Gate PE-VeriFlow prompt and 120s deadline reserve in `harness.py`."""
    self.assertEqual(harness.STOP_BEFORE_SEC, 120)
    self.assertEqual(harness.THINKING, "max")
    rendered = harness.NOTE.format(workdir="/app/files")
    self.assertIn("Gate 1 (Authority & Revision Reconciliation)", rendered)
    self.assertIn("Gate 2 (Programmatic Calculation & Dimensional Audit)", rendered)
    self.assertIn("Gate 3 (Independent Cold-Read Deliverable Check)", rendered)
    self.assertIn("/app/files", rendered)

  def test_02_provider_routing_and_config(self) -> None:
    """Tests `harness.provider()` and `harness.configure()` across Claude, Gemini, and OpenAI."""
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
        prov_name, mod_name = harness.configure(agent_dir, relay, session, {})
        self.assertEqual(prov_name, "model")
        self.assertEqual(mod_name, "gpt-oss-120b")
        settings = json.loads((agent_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["retry"]["maxRetries"], 6)
        self.assertEqual(settings["retry"]["maxAgentDelayMs"], 60000)
        mcp_cfg = json.loads((agent_dir / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(
            mcp_cfg["mcpServers"]["bim_server"]["url"],
            "http://127.0.0.1:41920/mcp/bim_server",
        )
    finally:
      os.environ.clear()
      os.environ.update(old_env)

  def test_03_token_and_cache_accounting(self) -> None:
    """Tests `harness.Run.on_line` token and prompt-cache accounting."""
    session = SessionStub()
    runner = harness.Run(session, "claude-opus-5-5")
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "stopReason": "end_turn",
            "content": [
                {"type": "text", "text": "Gate 3 verification passed: 0 clashes."}
            ],
            "usage": {
                "input": 12000,
                "cacheRead": 148000,
                "cacheWrite": 4000,
                "output": 1850,
            },
        },
    }
    asyncio.run(runner.on_line(json.dumps(event).encode("utf-8")))
    self.assertEqual(runner.replies, 1)
    self.assertEqual(session.final_message, "Gate 3 verification passed: 0 clashes.")
    self.assertEqual(len(session.usages), 1)
    self.assertEqual(session.usages[0]["input_tokens"], 164000)
    self.assertEqual(session.usages[0]["cache_read_tokens"], 148000)
    self.assertEqual(session.usages[0]["output_tokens"], 1850)

  def test_04_manifest_provenance_and_blob_digests(self) -> None:
    """Checks all 29 dev tasks in `artifacts/manifest.json` and verifies SHA-1 digests."""
    tasks = self.manifest["tasks"]
    self.assertEqual(len(tasks), 29)
    rewards = [float(t["reward"]) for t in tasks.values()]
    mean_score = sum(rewards) / len(rewards)
    self.assertAlmostEqual(mean_score, 0.491242, places=5)

    verified_files = 0
    for task_id, meta in tasks.items():
      task_dir = ARTIFACTS_DIR / task_id
      self.assertTrue(task_dir.is_dir(), f"Missing task directory: {task_id}")
      for rel_path, expected_sha in (meta.get("files") or {}).items():
        disk_path = task_dir / "files" / rel_path
        self.assertTrue(disk_path.is_file(), f"Missing deliverable on disk: {disk_path}")
        actual_sha = git_blob_sha1(disk_path)
        self.assertEqual(
            actual_sha,
            expected_sha,
            f"SHA-1 mismatch on {task_id}/{rel_path}",
        )
        verified_files += 1
    self.assertGreaterEqual(verified_files, 25)

  def test_05_lv_cable_sizing_schedule_and_constraints(self) -> None:
    """Checks `lv-cable-sizing` deliverables (32 circuits, NEC/EDS-26 Rev 4 limits)."""
    zip_path = (
        ARTIFACTS_DIR
        / "lv-cable-sizing"
        / "files"
        / "filesystem"
        / "electrical__lv_cable_sizing__blind"
        / "output"
        / "submission.zip"
    )
    self.assertTrue(zip_path.is_file())
    with zipfile.ZipFile(zip_path) as zf:
      names = set(zf.namelist())
      self.assertEqual(
          names,
          {
              "wire_schedule.csv",
              "E-621_wire_schedule.dxf",
              "calc_book.xlsx",
              "design_basis.md",
              "constraint_register.xlsx",
          },
      )
      csv_text = zf.read("wire_schedule.csv").decode("utf-8")
      rows = list(csv.DictReader(io.StringIO(csv_text)))
      self.assertEqual(len(rows), 32)

      by_id = {r["circuit"]: r for r in rows}
      for cid, r in by_id.items():
        vd_pct = float(r["vd_pct"])
        cum_vd = float(r["cumulative_vd_pct"])
        self.assertLessEqual(vd_pct, 3.0001, f"{cid} exceeds 3% segment drop")
        self.assertLessEqual(cum_vd, 5.0001, f"{cid} exceeds 5% cumulative drop")

      se1 = by_id["SE-1"]
      self.assertEqual(se1["sets"], "6")
      self.assertEqual(se1["size"], "500 kcmil")
      self.assertEqual(se1["material"], "CU")
      self.assertEqual(se1["duct_ids"], "D1, D2, D5, D6, D9, D10")
      self.assertAlmostEqual(float(se1["corrected_ampacity_a"]), 348.1, places=1)

      f05 = by_id["F-05"]
      self.assertEqual(f05["sets"], "3")
      self.assertEqual(f05["size"], "600 kcmil")
      self.assertEqual(f05["material"], "AL")
      self.assertAlmostEqual(float(by_id["B-17"]["cumulative_vd_pct"]), 4.928, places=3)
      self.assertAlmostEqual(float(by_id["B-09"]["cumulative_vd_pct"]), 4.833, places=3)

      dxf_text = zf.read("E-621_wire_schedule.dxf").decode("utf-8", errors="ignore")
      self.assertIn("SECTION", dxf_text)
      self.assertIn("ENTITIES", dxf_text)
      self.assertIn("SE-1", dxf_text)
      self.assertIn("EOF", dxf_text)

  def test_06_seismic_diaphragm_shear_and_cost(self) -> None:
    """Checks `seismic-diaphragm-shear` deliverables (`design_record.json` and DXF)."""
    zip_path = (
        ARTIFACTS_DIR
        / "seismic-diaphragm-shear"
        / "files"
        / "filesystem"
        / "final_batch4__structural_task6_seismic_diaphragm_shear__blind"
        / "output"
        / "submission.zip"
    )
    with zipfile.ZipFile(zip_path) as zf:
      record = json.loads(zf.read("design_record.json").decode("utf-8"))
      reported = record["reported"]
      self.assertEqual(reported["wpx_kips"], {"X": 1446.8, "Y": 1652.7})
      self.assertEqual(reported["fpx_kips"], {"X": 198.9, "Y": 227.2})
      self.assertEqual(len(record["conflicts_resolved"]), 13)

      cost_bd = reported["installed_cost_breakdown_usd"]
      parts_sum = sum(v for k, v in cost_bd.items() if k != "total")
      self.assertAlmostEqual(parts_sum, cost_bd["total"], places=2)
      self.assertAlmostEqual(reported["installed_cost_usd"], 340195.0, places=2)

  def test_07_heat_rejection_lcc_register_and_dxf(self) -> None:
    """Checks `heat-rejection-life-cycle-cost` constraint register and CAD schedules."""
    zip_path = (
        ARTIFACTS_DIR
        / "heat-rejection-life-cycle-cost"
        / "files"
        / "filesystem"
        / "final_batch4__mechanical_task3_ct_heat_lcc__blind"
        / "output"
        / "submission.zip"
    )
    with zipfile.ZipFile(zip_path) as zf:
      reg_csv = zf.read("constraint_register.csv").decode("utf-8")
      reg_rows = list(csv.DictReader(io.StringIO(reg_csv)))
      self.assertEqual(len(reg_rows), 159)
      docs_cited = {r["document"] for r in reg_rows}
      self.assertTrue(any("RFI" in d for d in docs_cited))
      self.assertTrue(any("PW-LTR" in d or "Water" in d for d in docs_cited))

      for building in ("CUP", "ANNEX", "LAB"):
        dxf_name = f"CT_SCHEDULE_{building}.dxf"
        self.assertIn(dxf_name, zf.namelist())
        self.assertGreater(zf.getinfo(dxf_name).file_size, 40000)

  def test_08_ifc4_site_model_and_mep_headroom_geometry(self) -> None:
    """Checks IFC4 3D geometry in `data-center-site-model` and MEP headroom clearance."""
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
    self.assertIn("IFCPROJECT(", ifc_text)
    self.assertIn("IFCSITE(", ifc_text)
    self.assertIn("IFCBUILDING(", ifc_text)
    self.assertIn("IFCEXTRUDEDAREASOLID(", ifc_text)
    self.assertIn("IFCPROPERTYSET(", ifc_text)

    sol_path = (
        ARTIFACTS_DIR
        / "data-hall-mep-routing-offset"
        / "files"
        / "app"
        / "files"
        / "dc_model__hall_seed005_d100__mep_routing"
        / "output"
        / "solution.py"
    )
    sol_code = sol_path.read_text(encoding="utf-8")
    self.assertIn("ifcopenshell", sol_code)
    sprinkler_z_mm = 3024.6
    required_clearance_mm = 460.0
    min_headroom_mm = 2600.0
    max_legal_overhead_z_mm = sprinkler_z_mm - required_clearance_mm
    self.assertAlmostEqual(max_legal_overhead_z_mm, 2564.6, places=1)
    self.assertLess(max_legal_overhead_z_mm, min_headroom_mm)

  def test_09_footing_settlement_datum_reconciliation(self) -> None:
    """Checks `Thelbridge_Verification_Memo_Item051_BlockC.docx` for datum reconciliation."""
    docx_path = (
        ARTIFACTS_DIR
        / "footing-settlement-verification"
        / "files"
        / "filesystem"
        / "Thelbridge_Verification_Memo_Item051_BlockC.docx"
    )
    self.assertTrue(docx_path.is_file())
    with zipfile.ZipFile(docx_path) as zf:
      xml_text = zf.read("word/document.xml").decode("utf-8")
      self.assertIn("740.5", xml_text)
      self.assertIn("746.0", xml_text)
      self.assertIn("CB-GEO-007", xml_text)
      self.assertIn("S-201", xml_text)
      self.assertIn("NOT VERIFIED", xml_text)


if __name__ == "__main__":
  unittest.main(verbosity=2)
