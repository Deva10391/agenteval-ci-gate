import json, os, sys
import typer
from .runner import run_golden
from .compare import compare, to_markdown
from .util import redact

app = typer.Typer(add_completion=False)

def _scores(golden, url):
    return run_golden(golden, url, os.getenv("TARGET_API_KEY", ""))

@app.command()
def run(
    golden: str = typer.Option("golden/p1_golden.jsonl"),
    baseline: str = typer.Option("baseline.json"),
    url: str = typer.Option("http://localhost:8000"),
    max_drop: float = typer.Option(5.0, help="Z%: fail if any metric is worse by more than this"),
):
    """Replay the golden set, score it, compare to baseline, exit 1 on regression."""
    try:
        new = _scores(golden, url)
        base = json.load(open(baseline))
        rows, failed = compare(new, base, max_drop)
        md = to_markdown(rows, max_drop)
        print(redact(md))
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(md + "\n")
        code = 1 if failed else 0
    except Exception as e:
        print(redact(f"AgentEval error: {e}"))
        code = 2  # an eval crash also blocks the merge
    sys.exit(code)

@app.command("update-baseline")
def update_baseline(
    golden: str = typer.Option("golden/p1_golden.jsonl"),
    baseline: str = typer.Option("baseline.json"),
    url: str = typer.Option("http://localhost:8000"),
):
    """Write current scores as the new baseline (run on main only)."""
    new = _scores(golden, url)
    json.dump(new, open(baseline, "w"), indent=2)
    print(redact(json.dumps(new)))

if __name__ == "__main__":
    app()
