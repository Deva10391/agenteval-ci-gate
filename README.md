# AgentEval CI Gate

> **Caught 2 of 2 seeded regressions (bad prompt, broken tool); the gate exits 1 and blocks the merge if any score gets worse by more than 5%.**

A CI gate that replays a golden test set against an LLM agent on every pull request and blocks the merge if quality, cost or latency gets worse.

**Requirements**
- Python 3.11+, Docker, Ollama with `qwen2.5:3b` (the judge), a GitHub repo with Actions.
- A target agent exposing `GET /health` and `POST /query` (or the included `mock_target.py`).
- A golden set in `golden/*.jsonl` and a `baseline.json`.

**Open-source utilities**
- Typer (CLI), httpx (calls), Ollama `qwen2.5:3b` (LLM-as-judge), FastAPI (mock target), GitHub Actions, Docker.

**Working amongst components**
```
PR opened -> replay golden set (3x per case) -> score -> compare to baseline -> pass or block merge
```
1. A PR triggers the GitHub Action, which builds and starts the agent.
2. The CLI replays every golden case against `/query`, 3 times each, and averages.
3. It scores 5 metrics and compares them to `baseline.json`.
4. Any metric worse by more than 5% (`--max-drop 5`) fails the build.
5. After a merge to `main`, the baseline is refreshed.

| Metric | How it is scored | Fails when |
|---|---|---|
| Task success | LLM judge (fixed prompt, temp 0) vs expected answer | drops > 5% |
| Tool-call accuracy | Tools called == expected tools | drops > 5% |
| Faithfulness | LLM judge: answer supported by retrieved context | drops > 5% |
| Cost | `cost_usd` per query from the target | rises > 5% |
| Latency | Measured wall time per query | rises > 5% |

**Details to know**
- Flaky scores: fixed judge prompt, temperature 0, fixed seed, 3 runs per case averaged.
- Safe failures: an unparsable judge reply scores 0, and an eval crash (exit 2) blocks the merge.
- Noise floor: latency changes under 0.25 s and cost changes under $0.0001 are ignored, so a 6% latency rise on a 0.02 s mock still passes.
- An escalation (ticket, no context) is not counted as unfaithful.
- Secrets live in GitHub Secrets and `redact()` masks them in all printed output.
- Baseline refreshes only after a merge to `main`, never on a PR.
- A gate only catches drops from a good baseline: record the baseline on the known-good build first.

**Simplified working:** PR → replay golden set → score → compare to baseline → pass or block.

## Proof: seeded regressions

Baseline recorded on the good mock (all five metrics at their best). Each break was committed on its own branch and replayed against that baseline.

| # | Branch | Seeded regression | Metric that caught it | Worse by | Gate result |
|---|---|---|---|---|---|
| 1 | `regress-prompt` | Bad prompt ("I do not know.") | task_success, faithfulness | 33.33% each | FAIL, exit 1 |
| 2 | `regress-tool` | Broken tool (`wrong_tool`) | tool_call_accuracy | 33.33% | FAIL, exit 1 |

On both branches cost and latency stayed within the noise floor and passed, so only the metrics that truly broke tripped the gate. One PR per branch runs the same check in GitHub Actions (`gate`); `main` is protected and requires it.

## Run

Run from the project root (the folder that contains `agenteval/`).

```bash
pip install -r requirements.txt
pip install fastapi uvicorn

# Terminal 1: mock target (proves the gate wiring only)
uvicorn mock_target:app --port 8001
```
```bash
# Terminal 2: local judge, then run the gate
ollama pull qwen2.5:3b
export TARGET_API_KEY="anything"
python -m agenteval.cli run --url http://localhost:8001 --max-drop 5
```
Exit codes: `0` pass, `1` regression, `2` eval crashed (also blocks the merge).

## Prove the gate (do in this order)
```bash
# 1. good baseline on main (mock running, unbroken)
printf '__pycache__/\n' > .gitignore
python -m agenteval.cli update-baseline --url http://localhost:8001
git add -A && git commit -m "good baseline" && git push -u origin main

# 2. seeded regression 1: bad answer
git checkout -b regress-prompt
sed -i 's/Use the .Forgot password. link on the login page and follow the emailed link./I do not know./' mock_target.py
git commit -am "bad prompt" && git push -u origin regress-prompt

# 3. seeded regression 2: broken tool
git checkout main && git checkout -b regress-tool
sed -i 's/"sql_orders"/"wrong_tool"/' mock_target.py
git commit -am "broken tool" && git push -u origin regress-tool
```
Open one PR per branch and screenshot the red ❌ `gate` checks. Locally: restart uvicorn after each `sed`, then `run` must print `exit=1`.

## Target contract
`POST /query` with header `x-api-key` and body `{"query": "..."}` returns:
```json
{"answer": "...", "tools": ["kb_search"], "contexts": ["..."], "cost_usd": 0.002}
```

## Golden set format
One JSON object per line in `golden/*.jsonl`:
```json
{"id":"kb-01","query":"How do I reset my password?","expected_answer":"...","expected_tools":["kb_search"]}
```

## Setup in GitHub
Use the root `agenteval.yml` (Ollama judge, no judge key) as `.github/workflows/agenteval.yml`. Add repo secrets `TARGET_API_KEY` and `LLM_API_KEY`, add a `Dockerfile.target` that builds your agent, protect `main`, and require the `gate` check.

## Troubleshooting
| Error | Cause | Fix |
|---|---|---|
| `exit=0` after seeding a break | uvicorn still serves the old code | Restart uvicorn after every edit to `mock_target.py` |
| New score far better than baseline | Baseline was recorded on a weaker build | Re-run `update-baseline` on the good build |
| `fatal: not a git repository` | No `git init` | `git init -b main` |
| `No module named 'agenteval'` | Not run from the project root | `cd` to the folder containing `agenteval/` |
| `Got unexpected extra arguments` | Typer too old for your Click | `pip install "typer>=0.15.4"` |
| `404 Not Found .../query` | Wrong port or no `/query` route | Fix `--url` or start the target |
| `Connection refused` | Target not running | Start it, or use `mock_target.py` |
| Judge connection error | Ollama not running or model not pulled | `ollama serve` and `ollama pull qwen2.5:3b` |

## When NOT to use an agent
A deterministic function needs unit tests, not an LLM judge; use this gate only where outputs vary run to run.

## Limits
- The shipped golden set has 3 cases and `baseline.json` comes from the mock target; grow the set and re-baseline on your real agent.
- SupportDesk's `/query` does not yet return `tools`, `contexts` or `cost_usd` and ignores `x-api-key`, so the gate passes only against the mock until those fields are added.
- The judge is a small local model and can be wrong; for harder cases set `JUDGE_MODEL` to a bigger one such as `qwen2.5:7b`, and keep the golden set small, clear and human-checked.
- Latency on shared CI runners is noisy; raise the latency threshold if it flaps.

## Files
`agenteval/cli.py` run, update-baseline · `runner.py` replay and scoring · `judge.py` fixed prompts · `compare.py` baseline compare · `util.py` key masking · `mock_target.py` stand-in agent