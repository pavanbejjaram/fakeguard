"""
FakeGuard v2 – FastAPI Backend
──────────────────────────────
Start: uvicorn main:app --reload --port 8000
Docs:  http://localhost:8000/docs
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, httpx
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models, schemas
from database import init_db, get_db
from auth     import hash_password, verify_password, create_access_token, get_current_user
from ml       import predict as ml_predict, reload_model
from features import router as feat_router

app = FastAPI(title="FakeGuard API v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(feat_router)

@app.on_event("startup")
def startup():
    init_db()
    from ml import get_model
    get_model()   # warm up / load model


# ══════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register", response_model=schemas.TokenResponse, status_code=201)
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(409, "Username already taken")
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    user = models.User(
        username  = body.username,
        email     = body.email,
        hashed_pw = hash_password(body.password),
    )
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"sub": user.username})
    return schemas.TokenResponse(access_token=token, username=user.username, email=user.email)


@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(401, "Invalid username or password")
    token = create_access_token({"sub": user.username})
    return schemas.TokenResponse(access_token=token, username=user.username, email=user.email)


@app.post("/api/auth/logout")
def logout(current_user: models.User = Depends(get_current_user)):
    return {"message": "Logged out successfully"}


@app.get("/api/auth/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "username":   current_user.username,
        "email":      current_user.email,
        "created_at": current_user.created_at,
    }


# ══════════════════════════════════════════════════════════════════════════
# NEWS CHECK
# ══════════════════════════════════════════════════════════════════════════

@app.post("/api/check", response_model=schemas.CheckResponse)
async def check_news(
    body:         schemas.CheckRequest,
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    # ── 1. ML prediction (always runs) ────────────────────────────────────
    ml_result = ml_predict(body.news_text)

    # ── 2. Claude AI (optional – only if api_key provided) ────────────────
    ai_verdict    = "UNCERTAIN"
    ai_confidence = 50
    ai_summary    = "No AI key provided – ML-only analysis."

    if body.api_key and body.api_key.startswith("sk-"):
        prompt = f"""You are an expert fake-news analyst with deep knowledge of media literacy.
Analyze the following news text carefully.

News text:
\"\"\"
{body.news_text[:3000]}
\"\"\"

Respond ONLY with a JSON object – no markdown fences, no extra text:
{{
  "verdict":    "REAL" | "FAKE" | "UNCERTAIN",
  "confidence": <integer 0-100>,
  "summary":    "<2-3 sentence plain-English explanation of your reasoning>"
}}"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key":         body.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type":      "application/json",
                    },
                    json={
                        "model":      "claude-sonnet-4-20250514",
                        "max_tokens": 400,
                        "messages":   [{"role": "user", "content": prompt}],
                    }
                )
            data   = resp.json()
            if "error" in data:
                raise ValueError(data["error"]["message"])
            raw    = "".join(b.get("text","") for b in data.get("content", []))
            parsed = json.loads(raw.replace("```json","").replace("```","").strip())
            ai_verdict    = parsed.get("verdict", "UNCERTAIN")
            ai_confidence = int(parsed.get("confidence", 50))
            ai_summary    = parsed.get("summary", "")
        except Exception as e:
            ai_summary = f"AI call failed: {str(e)[:100]}"

    # ── 3. Fuse ML + AI → final verdict ───────────────────────────────────
    v_score = {"FAKE": -1.0, "UNCERTAIN": 0.0, "REAL": 1.0}
    has_ai  = body.api_key and body.api_key.startswith("sk-")
    ml_w, ai_w = (0.45, 0.55) if has_ai else (1.0, 0.0)

    ml_s = v_score.get(ml_result["verdict"], 0) * ml_result["confidence"]
    ai_s = v_score.get(ai_verdict, 0) * (ai_confidence / 100)
    combined = ml_w * ml_s + ai_w * ai_s

    if   combined <= -0.25: final_verdict = "FAKE"
    elif combined >=  0.25: final_verdict = "REAL"
    else:                   final_verdict = "UNCERTAIN"
    final_score = round(abs(combined), 4)

    # ── 4. Persist ────────────────────────────────────────────────────────
    record = models.NewsCheck(
        user_id       = current_user.id,
        news_text     = body.news_text,
        ml_verdict    = ml_result["verdict"],
        ml_confidence = ml_result["confidence"],
        ml_fake_prob  = ml_result["fake_prob"],
        ml_real_prob  = ml_result["real_prob"],
        ml_model_name = ml_result["model"],
        ai_verdict    = ai_verdict,
        ai_confidence = ai_confidence,
        ai_summary    = ai_summary,
        final_verdict = final_verdict,
        final_score   = final_score,
    )
    db.add(record); db.commit(); db.refresh(record)

    return schemas.CheckResponse(
        id   = record.id,
        ml   = schemas.MLResult(
            verdict    = ml_result["verdict"],
            confidence = ml_result["confidence"],
            fake_prob  = ml_result["fake_prob"],
            real_prob  = ml_result["real_prob"],
            model      = ml_result["model"],
            signals    = schemas.MLSignals(**ml_result["signals"]),
        ),
        ai   = schemas.AIResult(
            verdict    = ai_verdict,
            confidence = ai_confidence,
            summary    = ai_summary,
        ),
        final_verdict = final_verdict,
        final_score   = final_score,
        checked_at    = record.checked_at,
    )


# ══════════════════════════════════════════════════════════════════════════
# HISTORY & STATS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/history")
def history(
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
    limit:        int         = 20,
):
    rows = (
        db.query(models.NewsCheck)
        .filter(models.NewsCheck.user_id == current_user.id)
        .order_by(models.NewsCheck.checked_at.desc())
        .limit(limit).all()
    )
    return [
        {
            "id":            r.id,
            "news_snippet":  r.news_text[:90] + ("…" if len(r.news_text) > 90 else ""),
            "final_verdict": r.final_verdict,
            "ml_verdict":    r.ml_verdict,
            "ai_verdict":    r.ai_verdict,
            "ml_confidence": r.ml_confidence,
            "ai_confidence": r.ai_confidence,
            "checked_at":    r.checked_at.isoformat(),
        }
        for r in rows
    ]


@app.get("/api/stats")
def stats(
    current_user: models.User = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    rows  = db.query(models.NewsCheck).filter(models.NewsCheck.user_id == current_user.id).all()
    total = len(rows)
    fake  = sum(1 for r in rows if r.final_verdict == "FAKE")
    real  = sum(1 for r in rows if r.final_verdict == "REAL")
    return {"total": total, "fake": fake, "real": real, "uncertain": total - fake - real}


@app.get("/api/model-info")
def model_info():
    """Returns info about the loaded ML model."""
    import os, json
    metrics_file = os.path.join(os.path.dirname(__file__), "ml", "artifacts", "metrics.json")
    if os.path.exists(metrics_file):
        with open(metrics_file) as f:
            return json.load(f)
    return {"status": "Model not trained yet. Run: python ml/train_model.py"}


@app.post("/api/reload-model")
def do_reload_model(current_user: models.User = Depends(get_current_user)):
    """Hot-reload the ML model after retraining."""
    model = reload_model()
    return {"message": f"Model reloaded: {getattr(model, 'model_name', 'fallback')}"}


@app.get("/")
def root():
    return {"service": "FakeGuard API", "version": "2.0", "status": "running"}
