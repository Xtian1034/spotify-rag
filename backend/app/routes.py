from flask import Blueprint, request

from .chat import answer

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.get("/health")
def health():
    return {"status": "ok"}

@bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return {"error": "question is required"}, 400
    return {"answer": answer(question)}

