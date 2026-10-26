from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.get("/health")
def health():
    return {"status": "ok"}

