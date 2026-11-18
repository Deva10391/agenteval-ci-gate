# AgentEval CI Gate

> **Blocks the merge if any metric gets worse by more than 5%.**

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
4. Any metric worse by more than 5% fails the build.
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
- Noise floor: latency changes under 0.25 s and cost changes under $0.0001 are ignored.
- An escalation (ticket, no context) is not counted as unfaithful.
- Secrets live in GitHub Secrets and `redact()` masks them in all printed output.
- Baseline refreshes only after a merge to `main`, never on a PR.

**Simplified working:** PR → replay golden set → score → compare to baseline → pass or block.

## Run

Run from the project root (the folder that contains `agenteval/`).

```bash
pip install -r requirements.txt

# Terminal 1: no real agent yet? Start the mock target (proves the gate wiring only)
pip install fastapi uvicorn
uvicorn mock_target:app --port 8001
```
```bash
# Terminal 2: local judge, then run the gate
ollama pull qwen2.5:3b
export TARGET_API_KEY="anything"
python -m agenteval.cli run --url http://localhost:8001 --max-drop 5
```
For the real thing, point `--url` at your running agent. Set a new baseline (run on `main` only):
```bash
python -m agenteval.cli update-baseline --url http://localhost:8001
```
Exit codes: `0` pass, `1` regression, `2` eval crashed (also blocks the merge).

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
| `No module named 'agenteval'` | Not run from the project root | `cd` to the folder containing `agenteval/` |
| `Got unexpected extra arguments` | Typer too old for your Click | `pip install "typer>=0.15.4"` |
| `404 Not Found .../query` | Wrong port or no `/query` route | Fix `--url` or start the target |
| `Connection refused` | Target not running | Start it, or use `mock_target.py` |
| Judge connection error | Ollama not running or model not pulled | `ollama serve` and `ollama pull qwen2.5:3b` |

## Limits
- The shipped golden set has 3 cases and `baseline.json` comes from the mock target; grow the set and re-baseline on your real agent.
- The judge is a small local model and can be wrong; for harder cases set `JUDGE_MODEL` to a bigger one such as `qwen2.5:7b`, and keep the golden set small, clear and human-checked.
- Latency on shared CI runners is noisy; raise 5% for latency if it flaps.
- Tool-call accuracy needs the target to report which tools it used.

## Files
`agenteval/cli.py` run, update-baseline · `runner.py` replay and scoring · `judge.py` fixed prompts · `compare.py` baseline compare · `util.py` key masking · `mock_target.py` stand-in agent