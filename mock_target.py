from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/query")
def query(body: dict):
    q = body["query"].lower()
    if "password" in q:
        return {"answer": "Use the 'Forgot password' link on the login page and follow the emailed link.",
                "tools": ["kb_search"], "contexts": ["Use the 'Forgot password' link on the login page and follow the emailed link."], "cost_usd": 0.001}
    if "order" in q:
        return {"answer": "Order 1001 is shipped and arrives in 2 days.",
                "tools": ["wrong_tool"], "contexts": ["order 1001: shipped, eta 2 days"], "cost_usd": 0.001}
    return {"answer": "Escalated to a human with a ticket.",
            "tools": ["create_ticket"], "contexts": [], "cost_usd": 0.001}
