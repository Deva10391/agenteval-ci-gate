import json, os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:3b")

# Fixed prompts: never edit casually, a change here shifts every score (re-baseline if you do).
SUCCESS_PROMPT = """You are a strict grader.
Question: {query}
Expected answer: {expected}
Actual answer: {answer}
Does the actual answer give the same facts as the expected answer?
Reply with JSON only: {{"score": 1}} or {{"score": 0}}"""

FAITH_PROMPT = """You are a strict grader.
Context: {context}
Answer: {answer}
Is every claim in the answer supported by the context?
Reply with JSON only: {{"score": 1}} or {{"score": 0}}"""

def _ask(prompt: str) -> float:
    r = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",                         # force valid JSON from the 3B model
            "options": {"temperature": 0, "seed": 0}, # deterministic judging
        },
        timeout=120,
    )
    r.raise_for_status()
    try:
        return float(json.loads(r.json()["message"]["content"])["score"])
    except Exception:
        return 0.0  # unparsable judge output counts as a fail, never a silent pass

def task_success(query, expected, answer) -> float:
    return _ask(SUCCESS_PROMPT.format(query=query, expected=expected, answer=answer))

def faithfulness(context, answer) -> float:
    if not context:  # no retrieved context: an answer is ungrounded, an escalation is fine
        return 1.0 if not answer else 0.0
    return _ask(FAITH_PROMPT.format(context="\n".join(context), answer=answer))
