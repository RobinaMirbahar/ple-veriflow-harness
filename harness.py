# Copyright 2026 Google LLC
# Modified 2026 Robina Mirbahar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PE-VeriFlow Pi coding agent harness (`@earendil-works/pi-coding-agent`).

Runs a headless Pi session per task with three concrete mechanisms:
1. Streaming prompt-cache warming (`cacheWarming: "streaming"`), 1-hour HTTP
   idle timeout for extended reasoning streams, and 8 exponential retries.
2. Explicit capability profiles (`MODEL_SPECS`) and reasoning effort routing
   across all eight sponsored `google-cloud/*` models and local BYO models.
3. A domain-agnostic programmatic Gate-3 cold-read deliverable auditor
   (`audit_deliverables`) that inspects generated artifacts inside the task
   container and runs one bounded remediation turn if structural, schema,
   formula, geometry, syntax, or empty-summary defects are found.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile
from typing import Any

import taskbridge

HERE = pathlib.Path(__file__).resolve().parent
PI = shutil.which("pi") or str(HERE / "node_modules" / ".bin" / "pi")
THINKING = "max"
WORK_RESERVE_SEC = 240
STOP_BEFORE_SEC = 90
MIN_RECOVERY_SEC = 150
CATALOG_TIMEOUT_SEC = 30
# Match pi-opus cache warming, backoff retries, and 1-hour silent stream limit.
SETTINGS = {
    "defaultProjectTrust": "never",
    "quietStartup": True,
    "cacheWarming": "streaming",
    "retry": {"maxRetries": 8, "baseDelayMs": 2000, "maxAgentDelayMs": 60000},
    "httpIdleTimeoutMs": 3_600_000,
}
# Request features the Google Cloud route for Claude refuses. pi leaves them
# out, and the Anthropic API works without them too.
COMPAT = {
    "supportsStrictTools": False,
    "supportsMidConvoEffort": False,
    "supportsMidConvoSystemMessages": False,
    "supportsMidConvoToolChanges": False,
}
# Fallback limits when a model is absent from both Pi's catalog and MODEL_SPECS.
UNKNOWN_MODEL = {"input": ["text"], "contextWindow": 128000, "maxTokens": 16384}
GEMINI_4_MODEL = {
    "input": ["text", "image"],
    "contextWindow": 1048576,
    "maxTokens": 65536,
}
MODEL_SPECS: dict[str, dict[str, Any]] = {
    "claude-opus-5-5": {
        "input": ["text", "image"],
        "contextWindow": 200000,
        "maxTokens": 32000,
    },
    "gemini-4-argon": dict(GEMINI_4_MODEL),
    "gemini-4-carbon": dict(GEMINI_4_MODEL),
    "gemini-4-hydrogen": dict(GEMINI_4_MODEL),
    "gemini-4-neon": dict(GEMINI_4_MODEL),
    "gemini-3.8-flash": dict(GEMINI_4_MODEL),
    "gemini-3.1-pro-preview": dict(GEMINI_4_MODEL),
    "gpt-oss-120b": {
        "input": ["text"],
        "contextWindow": 131072,
        "maxTokens": 32768,
    },
    "glm-5.2": {
        "input": ["text"],
        "contextWindow": 200000,
        "maxTokens": 32768,
    },
    "gemma-4-26b": {
        "input": ["text", "image"],
        "contextWindow": 262144,
        "maxTokens": 32768,
    },
    "llama-4-maverick": {
        "input": ["text", "image"],
        "contextWindow": 1048576,
        "maxTokens": 32768,
    },
}

NOTE = (
    "You are an autonomous Principal Physical Engineer working on a graded"
    " engineering task. Your tools act on the task's Linux container, whose"
    " working directory is {workdir}; it has no internet access.\n"
    "Follow the 3-Gate PE-VeriFlow Verification Protocol before finishing:\n"
    "1. Gate 1 (Authority & Revision Reconciliation): Inspect every file in"
    " {workdir}. Reject superseded revisions when a newer revision, RFI, or"
    " addendum governs, and reconcile drawing callouts against project"
    " specifications and governing code tables.\n"
    "2. Gate 2 (Programmatic Calculation & Dimensional Audit): Compute all"
    " engineering quantities with Python scripts rather than mental arithmetic."
    " Verify unit conversions (imperial/SI, psf/ksf, kcmil/ampacity, mm/ft)"
    " and elevation or coordinate datums.\n"
    "3. Gate 3 (Independent Cold-Read Deliverable Check): Write every required"
    " deliverable to the exact path and format requested, re-open saved files"
    " from disk with Python before exiting to verify zero empty or malformed"
    " outputs, and report exact file paths and governing design values."
)
TIME_NOTE = (
    " You have about {minutes} minutes in all; leave time to finish and check"
    " all deliverables."
)

# Executed inside the task container to snapshot modified files and run cold-read
# deliverable validation using only Python's standard library.
_CONTAINER_AUDIT_PY = r"""
import ast
import csv
import io
import json
import os
import pathlib
import sys
import xml.etree.ElementTree as ET
import zipfile

EXCEL_ERRORS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!")
IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules"}

def scan_files(roots):
  out = {}
  seen_dirs = set()
  for raw in roots:
    root = pathlib.Path(raw)
    if not root.exists():
      continue
    try:
      resolved = str(root.resolve())
    except OSError:
      resolved = str(root)
    if resolved in seen_dirs:
      continue
    seen_dirs.add(resolved)
    for cur, dirs, files in os.walk(root):
      dirs[:] = [d for d in sorted(dirs) if d not in IGNORE_DIRS]
      for fname in sorted(files):
        fpath = pathlib.Path(cur) / fname
        if fpath.is_symlink():
          continue
        try:
          st = fpath.stat()
          out[str(fpath)] = [st.st_size, st.st_mtime_ns]
        except OSError:
          continue
        if len(out) >= 25000:
          return out
  return out

def check_xlsx(data, label, defects):
  try:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
      names = set(zf.namelist())
      if "xl/workbook.xml" not in names:
        defects.append(f"{label}: missing xl/workbook.xml")
        return
      for name in names:
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
          xml_raw = zf.read(name)
          try:
            root = ET.fromstring(xml_raw)
          except ET.ParseError as exc:
            defects.append(f"{label} ({name}): invalid XML ({exc})")
            return
          for cell in root.iter():
            if (cell.tag == "c" or cell.tag.endswith("}c")) and cell.attrib.get("t") == "e":
              defects.append(f"{label} ({name}): Excel error cell")
              return
          xml_text = xml_raw.decode("utf-8", errors="ignore")
          for err in EXCEL_ERRORS:
            if f"<v>{err}</v>" in xml_text or f"<t>{err}</t>" in xml_text:
              defects.append(f"{label} ({name}): contains formula error {err}")
              return
  except zipfile.BadZipFile:
    defects.append(f"{label}: invalid XLSX ZIP container")

def check_docx(data, label, defects):
  try:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
      if "word/document.xml" not in zf.namelist():
        defects.append(f"{label}: missing word/document.xml")
        return
      ET.fromstring(zf.read("word/document.xml"))
  except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
    defects.append(f"{label}: invalid DOCX ({exc})")

def check_payload(ext, data, label, defects, depth=0):
  if len(data) == 0:
    defects.append(f"{label}: empty 0-byte deliverable")
    return
  if ext == ".zip" and depth == 0:
    try:
      with zipfile.ZipFile(io.BytesIO(data)) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        if not entries:
          defects.append(f"{label}: archive has zero files")
          return
        bad = zf.testzip()
        if bad is not None:
          defects.append(f"{label}: corrupt archive entry {bad}")
          return
        for info in entries[:64]:
          inner_ext = pathlib.Path(info.filename).suffix.lower()
          check_payload(inner_ext, zf.read(info.filename), f"{label}!{info.filename}", defects, depth + 1)
    except zipfile.BadZipFile:
      defects.append(f"{label}: corrupt ZIP archive")
  elif ext in (".xlsx", ".xlsm"):
    check_xlsx(data, label, defects)
  elif ext == ".docx":
    check_docx(data, label, defects)
  elif ext == ".json":
    try:
      json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
      defects.append(f"{label}: invalid JSON ({exc})")
  elif ext == ".csv":
    text = data.decode("utf-8", errors="replace").strip()
    if not text or sum(1 for _ in csv.reader(io.StringIO(text))) < 1:
      defects.append(f"{label}: empty CSV")
  elif ext == ".dxf":
    text = data.decode("utf-8", errors="replace")
    if "SECTION" not in text or "EOF" not in text:
      defects.append(f"{label}: incomplete DXF (missing SECTION/EOF)")
  elif ext == ".ifc":
    text = data.decode("utf-8", errors="replace")
    if "ISO-10303-21;" not in text or "END-ISO-10303-21;" not in text:
      defects.append(f"{label}: incomplete IFC (missing ISO-10303-21 wrapper)")
  elif ext == ".pdf":
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
      defects.append(f"{label}: invalid or truncated PDF")
  elif ext == ".py":
    try:
      ast.parse(data.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
      defects.append(f"{label}: Python syntax error ({exc})")

def main():
  req = json.loads(sys.stdin.read())
  mode = req["mode"]
  roots = req["roots"]
  current = scan_files(roots)
  if mode == "snapshot":
    print(json.dumps({"files": current}))
    return
  baseline = req.get("baseline") or {}
  changed = sorted(p for p, meta in current.items() if baseline.get(p) != meta)
  defects = []
  for path_str in changed:
    p = pathlib.Path(path_str)
    try:
      raw = p.read_bytes()
    except OSError as exc:
      defects.append(f"{path_str}: unreadable deliverable ({exc})")
      continue
    check_payload(p.suffix.lower(), raw, path_str, defects)
  print(json.dumps({"changed": changed, "defects": defects}))

if __name__ == "__main__":
  main()
"""


def model_limits(model: str) -> dict[str, Any]:
  """Returns capability limits for models absent from Pi's built-in catalog.

  Args:
    model: Bare model identifier (e.g. `gemini-4-argon`, `gpt-oss-120b`).

  Returns:
    Capability dictionary (`input`, `contextWindow`, `maxTokens`).
  """
  bare = model.split("/", 1)[-1].lower()
  if bare in MODEL_SPECS:
    return dict(MODEL_SPECS[bare])
  if bare.startswith("gemini-4-"):
    return dict(GEMINI_4_MODEL)
  return dict(UNKNOWN_MODEL)


def thinking_level(provider_name: str, model: str = "") -> str:
  """Returns the optimal Pi `--thinking` flag for `provider_name` and `model`.

  Per PLE `docs/models.md`, native Gemini API models reason deeper at `high`
  than `max`, while Claude and GLM support `max`.

  Args:
    provider_name: Pi provider identifier (`anthropic`, `google`, or `model`).
    model: Bare model identifier.

  Returns:
    The `--thinking` level string (`"max"` for Claude/GLM, else `"high"`).
  """
  low = model.lower()
  if provider_name == "anthropic" or "claude" in low or "glm" in low:
    return THINKING
  if provider_name == "google":
    return "high"
  return "high"


def note(session: taskbridge.Session) -> str:
  """Returns the system prompt appendix for `session`.

  Args:
    session: Active task session.

  Returns:
    Formatted `NOTE` for `session.workdir`, plus `TIME_NOTE` when timed.
  """
  left = session.time_left()
  text = NOTE.format(workdir=session.workdir)
  if left is None:
    return text
  return text + TIME_NOTE.format(minutes=max(1, int(left // 60)))


def provider() -> tuple[str, dict[str, Any]]:
  """Returns the Pi provider name and its `models.json` entry.

  Returns:
    A tuple of `(provider_name, provider_config)`.
  """
  if os.environ.get("ANTHROPIC_BASE_URL"):
    return "anthropic", {
        "baseUrl": os.environ["ANTHROPIC_BASE_URL"],
        "api": "anthropic-messages",
        "apiKey": "$ANTHROPIC_API_KEY",
        "compat": COMPAT,
    }
  if os.environ.get("GOOGLE_GEMINI_BASE_URL"):
    return "google", {
        "baseUrl": os.environ["GOOGLE_GEMINI_BASE_URL"] + "/v1beta",
        "api": "google-generative-ai",
        "apiKey": "$GEMINI_API_KEY",
    }
  return "model", {
      "baseUrl": os.environ["MODEL_BASE_URL"],
      "api": "openai-completions",
      "apiKey": "$MODEL_API_KEY",
  }


def in_catalog(name: str, model: str, env: dict[str, str]) -> bool:
  """Checks whether Pi's built-in model catalog recognizes `model`.

  If the probe hangs beyond `CATALOG_TIMEOUT_SEC` or fails, returns `False` so
  the model is configured explicitly using `model_limits(model)`.

  Args:
    name: Provider name (`anthropic`, `google`, or `model`).
    model: Model identifier string.
    env: Subprocess environment variables for the Pi CLI probe.

  Returns:
    `True` if `(name, model)` appears in `pi --list-models`, else `False`.
  """
  try:
    out = subprocess.run(
        [PI, "--offline", "--list-models", model],
        env=env,
        capture_output=True,
        text=True,
        timeout=CATALOG_TIMEOUT_SEC,
        check=False,
    ).stdout
  except (subprocess.TimeoutExpired, OSError):
    return False
  return any(line.split()[:2] == [name, model] for line in out.splitlines())


def configure(
    agent_dir: pathlib.Path,
    relay: taskbridge.Relay,
    session: taskbridge.Session,
    env: dict[str, str],
) -> tuple[str, str]:
  """Writes Pi's model, settings, and MCP configuration files for a task.

  Args:
    agent_dir: Directory where Pi reads its configuration files.
    relay: Local HTTP relay for the task container and its MCP servers.
    session: Active task session.
    env: Environment dictionary passed to Pi subprocesses.

  Returns:
    A tuple of `(provider_name, model_name)`.
  """
  model = os.environ["MODEL_NAME"]
  name, config = provider()
  models = agent_dir / "models.json"
  # `pi --list-models` reads the provider here
  models.write_text(json.dumps({"providers": {name: config}}))
  if not in_catalog(name, model, env):
    config["models"] = [{"id": model, "name": model, **model_limits(model)}]
    models.write_text(json.dumps({"providers": {name: config}}))
  (agent_dir / "settings.json").write_text(json.dumps(SETTINGS))
  servers = {
      s["name"]: {"url": relay.mcp_url(s["name"]), "timeout": 300}
      for s in session.mcp_servers
  }
  (agent_dir / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
  return name, model


def _audit_roots(workdir: str) -> list[str]:
  """Returns container roots scanned for new or modified task deliverables."""
  roots: list[str] = []
  for candidate in (workdir, "/app/output", "/filesystem"):
    if candidate and candidate not in roots:
      roots.append(candidate)
  return roots


async def _exec_container_audit(
    session: taskbridge.Session,
    mode: str,
    roots: list[str],
    baseline: dict[str, list[int]] | None = None,
    timeout_sec: int = 25,
) -> dict[str, Any]:
  """Executes `_CONTAINER_AUDIT_PY` inside the task container via `session.exec`."""
  if not hasattr(session, "exec"):
    return {}
  b64_script = base64.b64encode(_CONTAINER_AUDIT_PY.encode("utf-8")).decode("ascii")
  payload = json.dumps(
      {"mode": mode, "roots": roots, "baseline": baseline or {}}
  ).replace("__PE_VERIFLOW_JSON__", "__PE_VERIFLOW_JSON_ESCAPED__")
  py_exec = (
      f'import base64; exec(base64.b64decode("{b64_script}").decode("utf-8"))'
  )
  cmd = (
      'PY=$(command -v python3 || command -v python || true)\n'
      'if [ -n "$PY" ]; then\n'
      f'  "$PY" -c {shlex.quote(py_exec)} <<\'__PE_VERIFLOW_JSON__\'\n'
      f"{payload}\n"
      "__PE_VERIFLOW_JSON__\n"
      "fi"
  )
  try:
    res = await session.exec(cmd, timeout_sec=timeout_sec)
  except Exception:  # pylint: disable=broad-exception-caught
    return {}
  if res.get("exit_code") != 0:
    return {}
  raw = (res.get("output") or "").strip().splitlines()
  if not raw:
    return {}
  try:
    parsed = json.loads(raw[-1])
  except ValueError:
    return {}
  return parsed if isinstance(parsed, dict) else {}


async def snapshot_workdir(session: taskbridge.Session) -> dict[str, list[int]]:
  """Captures `{path: [size, mtime_ns]}` across task roots prior to execution."""
  res = await _exec_container_audit(
      session, "snapshot", _audit_roots(session.workdir), timeout_sec=15
  )
  files = res.get("files")
  return files if isinstance(files, dict) else {}


async def audit_deliverables(
    session: taskbridge.Session,
    baseline: dict[str, list[int]],
) -> list[str]:
  """Runs programmatic Gate-3 checks on deliverables and the final summary.

  Args:
    session: Active task session after the primary agent pass.
    baseline: File state mapping returned by `snapshot_workdir()`.

  Returns:
    List of human-readable defect descriptions; empty when checks pass.
  """
  res = await _exec_container_audit(
      session,
      "audit",
      _audit_roots(session.workdir),
      baseline=baseline,
      timeout_sec=30,
  )
  changed = res.get("changed") if isinstance(res.get("changed"), list) else []
  defects = list(res.get("defects") or [])
  msg = (session.final_message or "").strip()
  low = msg.lower()
  if not msg or msg == "[tool call]":
    defects.append(
        "final_message is empty or stopped on an unresolved [tool call]"
    )
  elif not changed and (
      len(msg) < 200
      or "let me check" in low[-80:]
      or not any(
          kw in low
          for kw in (
              "deliver",
              "saved",
              "wrote",
              "written",
              "created",
              "openproject",
              "email",
              "submission",
          )
      )
  ):
    defects.append(
        "zero deliverables written or modified and final_message appears"
        " incomplete"
    )
  return defects


class Run:
  """Tracks JSON stream events from a single Pi subprocess run."""

  def __init__(self, session: taskbridge.Session, model: str):
    self.session, self.model, self.replies = session, model, 0

  async def on_event(self, event: dict[str, Any]) -> None:
    """Processes a parsed JSON event from Pi, updating final message and usage.

    Args:
      event: Decoded JSON event dictionary from Pi's stdout stream.
    """
    kind, message = event.get("type"), event.get("message") or {}
    if kind == "message_end" and message.get("role") == "assistant":
      self.replies += 1
      text = "\n".join(
          b.get("text", "")
          for b in message.get("content") or []
          if b.get("type") == "text"
      )
      if text.strip():
        self.session.final_message = text.strip()
      if message.get("stopReason") == "error":
        await self.session.log(
            f"pi: model error: {message.get('errorMessage')}"
        )
      # input_tokens counts cached prompt tokens too
      u = message.get("usage") or {}
      await self.session.usage(
          self.model,
          input_tokens=u.get("input", 0)
          + u.get("cacheRead", 0)
          + u.get("cacheWrite", 0),
          output_tokens=u.get("output", 0),
          cache_read_tokens=u.get("cacheRead", 0),
      )
    elif kind == "tool_execution_start":
      await self.session.log(
          f"pi: {event.get('toolName')} {json.dumps(event.get('args'))[:300]}"
      )
    elif kind in ("auto_retry_start", "compaction_start"):
      await self.session.log(f"pi: {kind} {json.dumps(event)[:300]}")

  async def on_line(self, line: bytes) -> None:
    """Parses a raw stdout line from Pi as JSON and forwards it to `on_event`.

    Args:
      line: Raw line bytes emitted by Pi.
    """
    try:
      event = json.loads(line)
    except ValueError:
      return
    if isinstance(event, dict):
      await self.on_event(event)


async def _run_pi_pass(
    session: taskbridge.Session,
    prompt_bytes: bytes,
    *,
    stop_before_sec: float,
) -> tuple[Run, taskbridge.Finished]:
  """Spawns one isolated headless Pi session connected through `taskbridge.Relay`."""
  with tempfile.TemporaryDirectory(
      prefix="pi-",
      dir=os.environ.get("HOME") or None,
      ignore_cleanup_errors=True,
  ) as scratch:
    agent_dir, work = (
        pathlib.Path(scratch) / "agent",
        pathlib.Path(scratch) / "work",
    )
    agent_dir.mkdir()
    work.mkdir()
    async with taskbridge.Relay(session) as relay:
      env = relay.env()
      env.update(
          PI_CODING_AGENT_DIR=str(agent_dir),
          PI_OFFLINE="1",
          PI_SKIP_VERSION_CHECK="1",
          PI_TELEMETRY="0",
          NODE_NO_WARNINGS="1",
          TASK_WORKDIR=session.workdir,
      )
      name, model = await asyncio.to_thread(
          configure, agent_dir, relay, session, env
      )
      argv = [
          PI,
          "--print",
          "--mode",
          "json",
          "--no-session",
          "-nc",
          "-ns",
          "-np",
          "-na",
          "-e",
          str(HERE / "task-tools.ts"),
          "--provider",
          name,
          "--model",
          model,
          "--thinking",
          thinking_level(name, model),
          "--append-system-prompt",
          note(session),
      ]
      run = Run(session, model)
      done = await taskbridge.run_process(
          argv,
          session,
          env=env,
          cwd=str(work),
          on_line=run.on_line,
          stdin=prompt_bytes,
          stop_before_sec=stop_before_sec,
          log_prefix="pi: ",
      )
  return run, done


async def solve(session: taskbridge.Session) -> str:
  """Runs Pi on a single task with Gate-3 cold-read deliverable remediation.

  Args:
    session: Active task session.

  Returns:
    The final message produced by Pi.

  Raises:
    RuntimeError: If Pi exits before the model produces any assistant reply.
  """
  baseline = await snapshot_workdir(session)
  left_initial = session.time_left()
  primary_reserve = (
      WORK_RESERVE_SEC
      if left_initial is None or left_initial >= 900
      else STOP_BEFORE_SEC
  )
  run, done = await _run_pi_pass(
      session,
      session.instruction.encode("utf-8"),
      stop_before_sec=primary_reserve,
  )
  if not run.replies:
    raise RuntimeError(
        f"pi exited with {done.code} before the model answered:"
        f" {done.stderr[-2000:]}"
    )

  defects = await audit_deliverables(session, baseline)
  left_after = session.time_left()
  if defects and (
      left_after is None or left_after - STOP_BEFORE_SEC >= MIN_RECOVERY_SEC
  ):
    await session.log(
        f"pe-veriflow gate-3 audit found {len(defects)} defect(s): "
        + "; ".join(defects[:8])
    )
    bullet_list = "\n".join(f"- {d}" for d in defects[:12])
    remedy_prompt = (
        f"{session.instruction}\n\n"
        f"## Prior Attempt Summary\n{session.final_message or '(none)'}\n\n"
        "## Gate-3 Cold-Read Deliverable Defects Detected\n"
        f"Fix every issue below before finishing, verify the saved deliverables"
        f" from disk, and return the complete engineering summary:\n{bullet_list}"
    )
    fix_run, _ = await _run_pi_pass(
        session,
        remedy_prompt.encode("utf-8"),
        stop_before_sec=STOP_BEFORE_SEC,
    )
    if not fix_run.replies:
      await session.log(
          "pe-veriflow gate-3 remediation ended before producing a reply"
      )
  else:
    await session.log(f"pe-veriflow gate-3 audit: {len(defects)} defect(s)")

  return session.final_message or "(pi stopped without a final message)"
