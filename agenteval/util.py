import os, re

SECRET_PAT = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{20,})")

def redact(text: str) -> str:
    """Mask API keys (and any env secret values) before anything is printed."""
    text = SECRET_PAT.sub("***", str(text))
    for k in ("TARGET_API_KEY", "LLM_API_KEY"):
        v = os.getenv(k)
        if v:
            text = text.replace(v, "***")
    return text
