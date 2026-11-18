HIGHER_BETTER = ["task_success", "tool_call_accuracy", "faithfulness"]
LOWER_BETTER = ["cost_usd", "latency_s"]
# Ignore tiny absolute changes: a 0.02s -> 0.022s latency "rise" is noise, not a regression.
ABS_FLOOR = {"latency_s": 0.25, "cost_usd": 0.0001}

def compare(new: dict, base: dict, max_drop_pct: float):
    rows, failed = [], False
    for m in HIGHER_BETTER + LOWER_BETTER:
        b, n = base[m], new[m]
        if b == 0:
            change = 0.0
        elif m in HIGHER_BETTER:
            change = (b - n) / b * 100   # % drop
        else:
            change = (n - b) / b * 100   # % rise
        bad = change > max_drop_pct and abs(n - b) > ABS_FLOOR.get(m, 0.0)
        failed |= bad
        rows.append((m, b, n, round(change, 2), "FAIL" if bad else "ok"))
    return rows, failed

def to_markdown(rows, max_drop_pct):
    out = [f"### AgentEval (gate: worse by more than {max_drop_pct}% fails)",
           "| metric | baseline | new | worse by % | status |", "|---|---|---|---|---|"]
    out += [f"| {m} | {b} | {n} | {c} | {s} |" for m, b, n, c, s in rows]
    return "\n".join(out)