import json, time
import httpx
from statistics import mean
from . import judge

REPEATS = 3  # run each case 3 times and average, to damp flaky scores

def load_golden(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def call_target(url, key, query):
    t = time.perf_counter()
    r = httpx.post(f"{url}/query", json={"query": query},
                   headers={"x-api-key": key}, timeout=60)
    r.raise_for_status()
    d = r.json()
    d["latency_s"] = time.perf_counter() - t
    return d

def score_once(case, out):
    tools = set(out.get("tools", []))
    expected = set(case.get("expected_tools", []))
    return {
        "task_success": judge.task_success(case["query"], case["expected_answer"], out.get("answer", "")),
        "tool_call_accuracy": 1.0 if tools == expected else 0.0,
        # an escalation (ticket, no context) has nothing to ground, so it is not unfaithful
        "faithfulness": 1.0 if (not out.get("contexts") and "create_ticket" in tools)
                        else judge.faithfulness(out.get("contexts", []), out.get("answer", "")),
        "cost_usd": float(out.get("cost_usd", 0.0)),
        "latency_s": out["latency_s"],
    }

def run_golden(golden_path, url, key):
    cases = load_golden(golden_path)
    per_case = []
    for c in cases:
        runs = [score_once(c, call_target(url, key, c["query"])) for _ in range(REPEATS)]
        per_case.append({k: mean(r[k] for r in runs) for k in runs[0]})
    return {k: round(mean(pc[k] for pc in per_case), 4) for k in per_case[0]}
