# Build, check and submit a harness

You are helping a participant enter the harness competition.

Each entry is an agent harness that runs as a WebSocket server (`serve.py`) and solves held-out engineering tasks over the competition protocol. Participants pair their harness with a Google-sponsored model, a commercial model on their own API key (OpenAI, Anthropic, or Gemini), or a self-hosted model at an OpenAI-compatible endpoint. The leaderboard ranks each harness + model pair together.

Your goal is to build an entry the evaluation server can run, verify it locally with the kit, and run it on the dev set to generate `artifacts/`. The participant submits the harness and its dev-set artifacts on the portal.

Follow these steps in order and do not skip any checks:

1. Start from a sample submission in the competition repository that the organizers shared with the participant under `sample_submissions/` (Hermes Agent or Pi on Claude Opus 5.5, the Antigravity CLI on Gemini 3.8 Flash, or a custom harness on an OpenAI key or vLLM server), or from the participant's existing repository.
2. Write the harness and `submission.yaml` (Section 2) so they satisfy Sections 3 through 7.
3. Verify the entry locally with `python -m kit check` (Section 8), then run the dev set with `eval/run.py` to write `artifacts/` (Section 8). Fix any issues until every check passes.
4. Put any required API keys in `.env` (Section 6). Stage and commit everything (`git add -A`) so the harness and `artifacts/` share one commit, then push to GitHub.
5. Tell the participant the entry is ready to submit (Section 9). Each participant has 3 scored submissions in total, one in the queue or under evaluation at a time.

## 1. The entry

An entry is a single commit in a GitHub repository with this layout at its root:

```
submission.yaml      how to install and start the harness, and which model it calls
serve.py             the harness: a WebSocket server (any language works; the samples use Python)
.env                 API keys, if the model or harness needs any (private repository only)
artifacts/           what this harness produced on the dev set, written by eval/run.py (Section 8)
...                  anything else it needs: requirements.txt, prompts, or a vendored agent
```

When you submit, the evaluation server clones your commit, runs `install` inside a build container, and packages `/opt/harness` as the runtime bundle. For each task, it starts your `serve` command from that bundle in an isolated container alongside the task container and connects over WebSocket. Your harness calls its model and interacts with the task environment exclusively through the competition protocol (Section 7) to run commands, read and write files, and call MCP tools inside the task container.

Requirements:

- Use a public repository, or a private repository owned by the participant with the competition's GitHub App installed (granting read-only access to selected repositories). Any repository containing a `.env` file must be private. Private git submodules are not supported.
- The submit form reads `submission.yaml` at the submitted commit, falling back to `recipe.yaml` if `submission.yaml` is absent. A `recipe.yaml` written in the `submission.yaml` format is read and reviewed like `submission.yaml`; the earlier recipe format (last section) is kept for the organizers' reference entries and refused for participant submissions because it does not include dev-set artifacts.
- The submit form inspects `artifacts/` at the submitted commit and refuses commits without usable artifacts (Section 8). The build step excludes `artifacts/` from `/opt/harness`, so your running harness never sees it.
- The serve container can reach only its model endpoint. No other host is reachable, so web search and outside APIs are unavailable. The task container has no network access at all.
- Every task's prompt and files (including hidden test tasks) are sent to the model endpoint your harness calls. Make sure the participant is comfortable with their endpoint's logging policy, and never retain copies of task content.

## 2. submission.yaml

```yaml
name: my-harness                          # leaderboard entry name: 2-39 chars of a-z, 0-9, and -
model_api: google-cloud/claude-opus-5-5   # the model your harness calls (Section 3)
install: >-                               # optional; runs once at build time as root with internet access
  uv venv --python 3.12 /opt/harness/venv
  && uv pip install --python /opt/harness/venv/bin/python -r {src}/requirements.txt
serve: /opt/harness/venv/bin/python {src}/serve.py    # required; starts your server on $PORT
env:                                      # optional; non-secret settings as quoted strings
  LOG_LEVEL: "info"
```

| Field | Rules |
|---|---|
| `name` | 2 to 39 characters (`a-z`, `0-9`, `-`), starting with a letter or digit |
| `model_api` | `google-cloud/<id>`, `openai/<model>`, `anthropic/<model>`, `gemini/<model>`, or `openai-compatible/<model>` paired with `model_base_url` (Section 3) |
| `model_base_url` | Required with `openai-compatible/` (and forbidden otherwise): an `https://` base URL on a public DNS hostname, typically ending in `/v1` |
| `install` | Shell command; `{src}` expands to the repository checkout at `/opt/harness/src` |
| `serve` | Shell command; `{src}` and `{port}` are expanded (the port is also in `$PORT`); must have balanced shell quotes |
| `env` | `NAME: "value"` pairs, quoted as strings (unquoted `true`, `1.10`, or `0755` get parsed as booleans/numbers by YAML). Never put secrets here; put keys in `.env` (Section 6) |

Environment variables managed by the evaluator cannot be set in `env` (or in `.env`, other than your model API key): `PORT`, `HOME`, `USER`, proxy variables (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `NODE_USE_ENV_PROXY`), and the model variables listed in Section 3.
Any `{...}` placeholders other than `{src}` and `{port}` are passed through untouched to the shell. Unknown top-level keys are rejected, and `submission.yaml` must be at most 16 KiB. Do not include repository or commit fields; the portal records those automatically.

## 3. The model

`model_api` declares which model your harness uses and how it is billed:

| `model_api` | Served by | Required in `.env` | Host the serve container reaches |
|---|---|---|---|
| `google-cloud/<id>` | Google-sponsored models | Nothing (evaluator injects a per-submission key) | Sponsored model endpoint |
| `openai/<model>` | OpenAI (participant's account) | `OPENAI_API_KEY=...` | `api.openai.com` |
| `anthropic/<model>` | Anthropic (participant's account) | `ANTHROPIC_API_KEY=...` | `api.anthropic.com` |
| `gemini/<model>` | Google AI Studio (participant's account) | `GEMINI_API_KEY=...` | `generativelanguage.googleapis.com` |
| `openai-compatible/<model>` + `model_base_url` | Self-hosted server (vLLM, SGLang, etc.) | `MODEL_API_KEY=...` | Host of `model_base_url` |

Available Google-sponsored models (all support tool calling):

| `model_api` | Model |
|---|---|
| `google-cloud/gemini-4-argon` | Gemini 4 Argon |
| `google-cloud/gemini-3.8-flash` | Gemini 3.8 Flash |
| `google-cloud/gemini-3.1-pro-preview` | Gemini 3.1 Pro (preview) |
| `google-cloud/claude-opus-5-5` | Claude Opus 5.5 |
| `google-cloud/gpt-oss-120b` | gpt-oss 120B |
| `google-cloud/qwen3-coder-480b` | Qwen3 Coder 480B A35B |
| `google-cloud/qwen3-next-80b` | Qwen3-Next 80B A3B Instruct |
| `google-cloud/deepseek-v3.2` | DeepSeek-V3.2 |
| `google-cloud/kimi-k2-thinking` | Kimi K2 Thinking |
| `google-cloud/minimax-m2` | MiniMax M2 |
| `google-cloud/glm-5.2` | GLM 5.2 |
| `google-cloud/gemma-4-26b` | Gemma 4 26B A4B |
| `google-cloud/llama-4-maverick` | Llama 4 Maverick 17B 128E |

At runtime, the serve container receives the same set of environment variables regardless of provider:

| Variable | Value |
|---|---|
| `PORT` | Port your WebSocket server must listen on |
| `MODEL_API` | Full `model_api` string from `submission.yaml` |
| `MODEL_NAME` | Bare model identifier to send in API requests (e.g. `claude-opus-5-5`) |
| `MODEL_BASE_URL`, `MODEL_API_KEY` | OpenAI-compatible base URL (usually ending in `/v1`) and API key, populated for every model |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY` | Identical to `MODEL_BASE_URL` and `MODEL_API_KEY`, so the standard OpenAI SDK works with zero configuration |
| `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY` | Populated for Claude models: Anthropic Messages API base URL (no `/v1`) and key |
| `GOOGLE_GEMINI_BASE_URL`, `GEMINI_API_KEY` | Populated for Gemini models: Gemini API base URL (no `/v1`) and key |
| `env` and `.env` entries | Passed through as written |

If you use `openai-compatible/`, your endpoint must accept `Authorization: Bearer <MODEL_API_KEY>`, support `tools` and `tool_calls` on `POST /v1/chat/completions` (for vLLM, pass `--enable-auto-tool-choice` and the appropriate `--tool-call-parser`), handle both streaming and non-streaming requests, and serve concurrent tasks. The egress proxy blocks hostnames that resolve to private IP ranges.

Model call tips:

- Stream long responses or set generous timeouts, since extended reasoning turns can stay quiet for several minutes.
- Retry 429 rate limits, network timeouts, and 5xx errors with exponential backoff. Do not retry 400 errors.
- Google-sponsored models default to their highest reasoning level (`max` for Claude and GLM; `high` for Gemini, gpt-oss, Kimi, and MiniMax) on both the evaluation server and `kit/model_proxy`. Pass `reasoning_effort` explicitly to use a lower level.
- Claude Opus 5.5 rejects `temperature`, `top_p`, `top_k`, and `thinking` blocks with `budget_tokens`, so omit them. Set a generous `max_tokens` (32,000 is a good default).
- Claude caches a prompt prefix only where the request marks it: put `"cache_control": {"type": "ephemeral"}` on the system prompt and on the newest message (Claude allows 4 such marks). Without the marks every turn pays the full input price for the whole conversation, which is many times the cost; the `minimal`, `plan-verify` and `node-protocol` samples show how. Gemini, OpenAI and vLLM cache on their own.
- Gemini 4 Argon accepts a thinking level (`low`, `medium`, or `high` via `reasoning_effort`) and returns HTTP 400 if given a `thinkingBudget`. On the native Gemini API, `high` thinks longer than `MAX`. Keep `max_tokens` at or below 65,536.
- Track elapsed time against `limits.agent_timeout_sec` and wrap up model calls before the deadline.

## 4. The build container (`install`)

- Runs once in a clean `debian:bookworm` container as `root`, with internet access and no task data, subject to a 30-minute timeout.
- Your repository is checked out at `/opt/harness/src` (the initial working directory). `$HOME` is a temporary scratch directory.
- Preinstalled tools include `uv` (`/opt/harness/bin/uv`), Node 22 (`/opt/harness/node`, where `npm -g` installs packages), `git`, `curl`, standard build tools, and `python3`.
- Only `/opt/harness` is archived into the runtime bundle (up to 2 GiB compressed / 8 GiB unpacked), and all symlinks must resolve inside `/opt/harness`. System packages installed outside `/opt/harness` (e.g., via `apt-get`) are discarded after the build. Your git repository (including full history) must be at most 1 GiB: every committed version of `artifacts/` stays in git history, so keep artifacts compact or squash history if it grows.
- Pin dependency versions for reproducible builds. The serve container uses the same base image, so binaries built during `install` run identically at evaluation time.

## 5. The serve container (`serve`)

- Each task starts a fresh container from the base image with your `/opt/harness` bundle mounted read-only. Your `serve` command runs in `/opt/harness/src` as uid 1000 with writable `/tmp` and `$HOME` tmpfs mounts (1 GB each), 2 CPUs, 4 GB RAM, and a 512-process limit.
- Listen on `0.0.0.0:$PORT` within 120 seconds. If your server fails to accept a WebSocket connection in time, the task fails and counts against your score. Each container serves one WebSocket connection for one task.
- Route all outbound traffic through `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` (`NODE_USE_ENV_PROXY=1` is pre-set for Node.js). Standard Python (`requests`, `httpx`), OpenAI, Anthropic, and Google SDKs use these environment variables automatically. Direct DNS resolution is disabled; the proxy resolves hostnames for you. Runtime package downloads are blocked.
- Standard output and standard error are captured as the serve log.

## 6. Keys: `.env`

Place all API keys in a `.env` file at the root of your repository, with one `NAME=value` per line:

```
OPENAI_API_KEY=sk-...
```

- Include the model API key Section 3 requires (none for `google-cloud/`). Variables are injected into the serve container's environment at runtime; the `.env` file itself is never copied into the bundle.
- Commit `.env` to a private repository with the competition's GitHub App installed. Public repositories containing a `.env` file are rejected (if you ever push a key to a public repo, revoke it immediately).
- If `.env` is gitignored, force-add it with `git add -f .env`.
- Keep each value on a single line without variable interpolation (`${...}`). Evaluator-reserved variable names (Section 2) are rejected except for the required model key. Limits: at most 32 variables and 16 KiB.

## 7. The protocol

Each task communicates over a single WebSocket connection using UTF-8 JSON text frames (up to 16 MiB per frame, one JSON object per frame). The evaluator sends the opening message:

```json
{"type": "task", "protocol": 1, "session": "3f2c9a1e0b7d4c55", "instruction": "<the task, verbatim>",
 "workdir": "/app",
 "limits": {"agent_timeout_sec": 21600, "exec_timeout_sec": 600, "max_output_bytes": 100000,
            "max_write_bytes": 10000000},
 "mcp_servers": [{"name": "apps", "url": "http://127.0.0.1:8000/mcp/", "transport": "streamable-http"}]}
```

Your server then sends action requests, each with a unique `id` of your choice (up to 8 run concurrently and the rest queue), and receives a matching `{"type": "result", "id": ...}` response:

| Request | Result |
|---|---|
| `{"type": "exec", "id": "1", "command": "ls -la", "timeout_sec": 120}` | `exit_code`, `output` (combined stdout/stderr; head and tail preserved past 100 KB), `truncated`, `timed_out` |
| `{"type": "read_file", "id": "2", "path": "/app/data.csv"}` | `ok`, `content_b64`, `size`, `truncated` (capped at 10 MB) |
| `{"type": "write_file", "id": "3", "path": "/app/out/report.md", "content_b64": "...", "append": false}` | `ok`, `size`; creates parent directories automatically; up to 10 MB per call |
| `{"type": "http", "id": "4", "method": "POST", "url": "<an mcp_servers URL>", "headers": {}, "body_b64": "..."}` | `ok`, `status`, `headers`, `body_b64`, `truncated`; bodies up to 10 MB |

Protocol details:

- `exec` runs `bash -c` inside the task container starting in `workdir` as the task user. Only filesystem state persists across calls (working directory changes via `cd` and shell variables do not). Commands time out at `min(timeout_sec, exec_timeout_sec, remaining_task_time)` (default `timeout_sec`: 120), returning `timed_out: true` and `exit_code: 124`.
- File paths may be absolute or relative to `workdir`, and file contents are base64-encoded in both directions. To write files larger than 10 MB, split them across multiple `write_file` calls with `append: true`.
- `http` reaches only the task's declared `mcp_servers` (if any) inside the task container. These servers use Streamable HTTP MCP; `tools/list` responses on some tasks include hundreds of tools and exceed 500 KB.
- Failed operations return `ok: false` with an `error` message. Malformed frames also return an error without aborting the task, but more than 20 malformed frames end the session.

One-way messages from your harness (no reply):

- `{"type": "log", "text": "..."}`: appends a line to the trial log.
- `{"type": "usage", "model": "...", "input_tokens": N, "output_tokens": N, "cache_read_tokens": N}`: reports token usage for a model call.
- `{"type": "done", "final_message": "..."}`: finishes the task cleanly.
- `{"type": "error", "message": "..."}`: aborts the task early (any files already written in the container are still graded).

When the task time limit expires, the evaluator sends `{"type": "cancel", "reason": "timeout"}` and closes the WebSocket 10 seconds later. On receiving `cancel`, stop in-flight model calls immediately and send `done` with your best summary; both `final_message` and any files on disk still count. If the socket closes before `done` or `error` (or if your server never listens), the task fails and counts against your harness.

Failures on the evaluator's side are retried, up to three attempts per task; a task still without a result counts 0 in that test run, and a test run in which no task could be graded runs again, keeping the runs already scored. For Google-sponsored models, endpoint outages, timeouts, and rate limits are evaluator faults; for self-hosted or BYO-key models, endpoint errors and outages count against your entry. For any model, an invalid request from your harness (such as a 400 error) counts against your entry. A harness that exits with an error before its model produces any output is treated as not started and run again, up to three attempts in all; if it never starts, the task counts 0.

See `sample_submissions/taskbridge.py` in the competition repository for a ready-to-use implementation (WebSocket server, per-task session handling, cancellation, and a local subprocess relay), or `docs/protocol.md` for the full specification.

## 8. Local checks

How tasks are graded:

- Graders inspect the exact deliverable file paths, names, and formats requested in the task instruction. Deliverables account for the vast majority of every score.
- Rubric judges also read `done.final_message` alongside the deliverable files. Always finish with a concise summary of what you produced and where each file is saved.

High-scoring harnesses read the full instruction carefully before acting, inspect the starting files in `workdir`, work in small verified steps, write an initial deliverable early and refine it, and budget time so they always send `done` before `agent_timeout_sec`.

The local kit in the competition repository runs the same checks as the evaluation server. You need `uv` and a local Docker daemon (remote `DOCKER_HOST` endpoints are rejected because the kit bind-mounts local directories). Containers run as `linux/amd64` (emulated on Apple Silicon). Running the dev set also requires Harbor (`uv tool install harbor==0.20.0 --with websockets`). Keep your entry in its own git repository beside the competition repository; inside the clone, `kit check` warns and never reports it ready to submit. From the competition repository root:

```bash
cp -r sample_submissions/pi-opus ../my-harness && git -C ../my-harness init   # a starting point of its own
uv run python -m kit check ../my-harness [--cancel-test] [--rebuild]
uv run python eval/run.py ../my-harness       # run and score the dev set, writing ../my-harness/artifacts/
```

If your harness files and `install` command have not changed since the last build, the cached bundle is reused automatically (pass `--rebuild` to force a fresh build). If the LLM judge fails during a dev-set run, `eval/run.py` reports the error and exits non-zero; after fixing your judge setup, re-run grading without repeating the trials via `uv run python eval/run.py --regrade runs/<name>-<time>`.

| `kit check` stage | What it verifies |
|---|---|
| `submission.yaml` | Validates all schema and field rules from Section 2 |
| `files` | Confirms files referenced by `serve` are committed, scans for leaked API keys outside `.env`, and warns on uncommitted changes |
| `.env` | Validates `.env` syntax (Section 6) and checks that the required model API key is present |
| `build` | Runs `install` in the builder container and packs `/opt/harness` into a valid bundle |
| `model` | Sends a one-line test prompt from inside the serve container through the egress proxy to verify model connectivity |
| `listen` | Confirms `serve` binds and accepts a WebSocket connection on `$PORT` within 120 seconds |
| `smoke` | Runs an end-to-end smoke task where the harness writes `/app/hello.txt` and sends `done` |
| `cancel` | *(With `--cancel-test`)* Cancels a running task after 45 seconds and verifies the harness cleanly sends `done` |
| `artifacts` | Checks that `artifacts/` passes all server validation rules and is committed (warns if not generated yet) |

Detailed logs are written to `~/.cache/pele/<name>/`: `build.log`, `serve.log`, `egress.log` (allowed and blocked outbound connections), `relay.log` (protocol requests and responses), and `check.json`. To test a `google-cloud/` model locally, start the local Vertex AI proxy in your own Google Cloud project with `kit/model_proxy/start.sh` (`VERTEXAI_PROJECT`, `MODEL_PROXY_URL`, `MODEL_PROXY_KEY`). Additional kit subcommands: `python -m kit validate`, `build`, `up`, and `models`.

### Dev-set artifacts

Every submission must include an `artifacts/` directory in the same commit as the harness, holding the outputs your harness produced on the dev set. Running `eval/run.py <entry>` generates `<entry>/artifacts/` automatically (one subfolder per dev task with `files/<container path>`, `final_message.md`, and a top-level `manifest.json` recording the run and harness state). Never create or edit `artifacts/` by hand.

```bash
uv run python eval/run.py ../my-harness                  # runs the dev set and writes ../my-harness/artifacts/
uv run python eval/run.py ../my-harness --tasks <id>     # reruns a single task, keeping the other task folders
uv run python -m kit artifacts ../my-harness             # validates artifacts/ against the evaluation server's rules
uv run python eval/run.py --artifacts ../my-harness      # grades committed artifacts as the server does; only the judge is called
git -C ../my-harness add -A && git -C ../my-harness commit -m "dev artifacts"   # commit everything together
```

When you submit, the evaluation server runs four steps in order: it builds the harness and runs the smoke task; grades the committed artifacts with the dev-set graders to compute the dev score (any task without usable artifacts counts 0); runs the harness live on a few randomly sampled dev tasks to verify that its scores reproduce (entries scoring well below their committed artifacts are flagged for organizer review); and runs the harness on the hidden test set, whose score ranks the leaderboard. Your harness runs three times on the hidden test set, all at once, and your test score is the mean of the three runs. A submission that fails the build or smoke step stops there and is not graded.

At submit time, the submit form refuses any commit that:

- Lacks an `artifacts/` folder,
- Substitutes an archive (`artifacts.zip`, `.tar.gz`, etc.) instead of an unpacked directory,
- Tracks artifact files with Git LFS,
- Exceeds 512 MiB or 10,000 files in `artifacts/`, or
- Submits a folder in which no dev task has usable artifacts.

Individual dev tasks with a missing folder, a symlink, a file over 95 MiB, or no gradable deliverables score 0. Whenever you modify your harness, rerun the dev set and commit everything together (`git add -A`): `manifest.json` hashes all harness files, and the server checks that your submitted code matches the harness that generated `artifacts/` (a change to README, LICENSE or CHANGELOG files alone gives a note instead of a warning). See `docs/artifacts.md` in the competition repository for the full rules.

Before submitting, confirm that every `kit check` stage passes, `eval/run.py` completed with deliverables in the expected paths, and `kit artifacts` accepts your committed `artifacts/` directory.

## 9. Submit and track

1. Commit and push all changes to GitHub. Record the commit SHA via `git rev-parse HEAD`.
2. The participant opens the portal's Submit page (`/competition/submit`), selects the repository and branch, reviews the checks, and submits.
3. The submission page tracks progress through `queued`, `validating` (commit and artifact structure checks), `building`, `smoke`, `running` (the dev artifacts are graded, then the reproduction, then the test set), `grading`, and finally `scored` or `failed`. It also shows the dev score and reproduction verdict (`pending`, `consistent`, `flagged`, `unmeasured`, or `not_run`). If a submission fails, inspect the failure reason and build/smoke logs, fix the issue, push a new commit, and resubmit. After a failure on the evaluator's side (`failed`, reason `error`) with test runs already in (the submission page says they are kept), do not resubmit: an organizer re-queues it, and only the missing runs run.

A submission reserves a slot as soon as it is queued. If it fails before reaching `running` (`invalid`, `build_failed`, or `smoke_failed`) or fails due to an evaluator error, the slot is returned. A participant can have one submission in the queue or under evaluation at a time, and can submit the next one once it is `scored` or `failed`. An evaluation takes about a day once it starts, and up to about three days when a harness uses most of the 6-hour limit on many tasks; time in the queue comes on top.

If the entry uses the participant's own API key or model server, the participant pays for every model call the evaluation server makes: the smoke task, the reproduction check on a few dev tasks, and the hidden test set three times, including any task or run repeated after a fault on the evaluator's side. The key's rate limits or the server must sustain about 36 tasks at once; 429s and timeouts from that key or server count against your entry.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| refused: *has no submission.yaml at its root* | Commit `submission.yaml` at the root of the repository, push, and verify the branch/SHA |
| refused: *.env ...* | Fix the `.env` issue reported (Section 6); remember that any repo with `.env` must be private |
| refused: *no artifacts/ folder* | Run `eval/run.py` on your entry, then stage and commit everything (`git add -A`) |
| refused: *an archive* or *Git LFS tracks* | Commit `artifacts/` as a normal unpacked directory without Git LFS (`git lfs untrack`) |
| refused: *no dev task in artifacts/ has usable artifacts* | Run `python -m kit artifacts` to see what failed in each task folder; fix or rerun the dev set |
| A dev task counts 0: *missing* or *refused* | Rerun that task with `eval/run.py --tasks <id>` and verify with `python -m kit artifacts` |
| *the harness changed after these artifacts were made* | Rerun the dev set with your updated harness, then commit everything together (`git add -A`) |
| Build failed: *could not clone* | Verify the repo URL and pushed commit SHA; for private repos, ensure the GitHub App is installed on the participant's account |
| Build failed otherwise | Inspect the build log; run `python -m kit check` locally to reproduce |
| Smoke failed: the server never listened | Bind to `0.0.0.0:$PORT` (not `127.0.0.1`) within 120 s; install dependencies under `/opt/harness` and invoke binaries by full path |
| Smoke failed: connection refused or 403 from a host | The serve container reaches only your model's endpoint: remove calls to other hosts, and make sure your HTTP client uses `HTTPS_PROXY` |
| Smoke failed: 401 from the model | Check that your API key in `.env` is valid and uses the exact variable name from Section 3 |
| *socket closed*, `harness:AgentTimeoutError` | Send `done` before `agent_timeout_sec` expires; stream long model calls and enforce a step time budget |
| Low score despite completing the run | Double-check exact deliverable paths and filenames in the task prompt, and include a clear summary in `done.final_message` |

## 11. Fair play

Do not hard-code task solutions or write logic that fingerprints specific tasks. Committed `artifacts/` must be the unaltered output of your submitted harness, without precomputed answers to dev or test tasks. Do not bypass network restrictions, inspect grading scripts, or tamper with the evaluation container. Your declared `model_api` must match the model your harness calls, and you must not retain or share task contents. Organizers audit top-ranking code and artifacts before publishing final results.

## Recipe configuration (`recipe.yaml`)

An earlier configuration format, `recipe.yaml`, defines `source` (`repo` and `ref`), `run.install`, and either:

- A `serve` section (`command`, `egress`) with a free-text `model` field (keys in `.env`, or the competition's model via `{proxy_url}` and `{proxy_key}` in `env`), or
- A `run.command` string that executes directly inside each task container using the competition's fixed model (`anthropic/claude-opus-5-5`) through the competition proxy.

The portal reads `recipe.yaml` when a commit has no `submission.yaml`. Only organizers may submit one in this earlier format (for baseline reference entries), and they validate it with `python -m portal.kit`. Participants submit `submission.yaml` together with their dev-set artifacts.
