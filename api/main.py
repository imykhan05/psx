"""
PSX AI Scanner — FastAPI backend (Phase 2 #4).

A thin, read-only HTTP layer over the scanner's existing output. It does NOT
recompute anything — it serves the files the pipeline already produces
(daily_signal.json, full_market_scan.csv, top_buys.csv, sentiment_cache.json)
and forwards free-text questions to the NL query engine.

AUTH
  A single shared API key checked via the `X-API-Key` header (the "simple, one
  key, not a full user system" gate that was requested). A real per-user
  JWT/auth system is deliberately deferred — it is a strategic, data-model
  decision (ROADMAP F2.3), not something to improvise here. Set the key with
  the PSX_API_KEY env var (or .env); it falls back to a clearly-labelled dev key.

ERRORS
  Every failure returns clean JSON ({"error": ..., "detail": ...}) — never a
  raw traceback. An exception handler enforces this even for unexpected errors.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# Reuse the engine's data locations and helpers — single source of truth.
from app.engines.nl_query_engine import (
    MODEL,
    DAILY_SIGNAL,
    SENTIMENT_CACHE,
    TOP_BUYS,
    FULL_SCAN,
    _read_json,
    _read_csv,
    load_context,
    build_system_prompt,
    get_client,
    stream_answer,
)

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEV_API_KEY = "psx-dev-key-change-me"
API_KEY = os.environ.get("PSX_API_KEY", DEV_API_KEY)

# Comma-separated allowed origins; "*" for open dev access.
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("PSX_CORS_ORIGINS", "*").split(",") if o.strip()
]

app = FastAPI(
    title="PSX AI Scanner API",
    version="1.0.0",
    description="Read-only HTTP access to the PSX scanner's end-of-day output.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth (shared API key via header)
# ---------------------------------------------------------------------------
def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


# ---------------------------------------------------------------------------
# Clean error handling — no raw tracebacks
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "request_error", "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": f"{type(exc).__name__}: {exc}"},
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
WEBUI_FILE = Path(__file__).resolve().parent / "webui.html"


@app.get("/", include_in_schema=False)
def home():
    """Built-in web UI: open the URL, enter the API key, see the data.

    The page itself loads without a key; it prompts for the key and then calls
    the same-origin endpoints below with the X-API-Key header.
    """
    if WEBUI_FILE.exists():
        return FileResponse(WEBUI_FILE, media_type="text/html")
    return JSONResponse({"service": "psx-ai-scanner-api", "docs": "/docs"})


@app.get("/health")
def health() -> dict:
    """Liveness + which data artifacts are present. No auth (health checks are open)."""
    files = {
        "daily_signal": DAILY_SIGNAL.exists(),
        "full_market_scan": FULL_SCAN.exists(),
        "top_buys": TOP_BUYS.exists(),
        "sentiment_cache": SENTIMENT_CACHE.exists(),
    }
    return {
        "status": "ok",
        "service": "psx-ai-scanner-api",
        "version": app.version,
        "data_files": files,
    }


@app.get("/signal", dependencies=[Depends(require_api_key)])
def get_signal() -> dict:
    """Today's daily market signal (verdict, confidence, reasons, top opportunities)."""
    signal = _read_json(DAILY_SIGNAL)
    if not signal:
        raise HTTPException(status_code=404, detail="No daily signal available. Run the scanner first.")
    return signal


@app.get("/opportunities", dependencies=[Depends(require_api_key)])
def get_opportunities(limit: int = 100) -> dict:
    """Top opportunities (top_buys.csv) as JSON records."""
    df = _read_csv(TOP_BUYS)
    if df.empty:
        return {"count": 0, "opportunities": []}
    records = df.head(max(1, min(limit, len(df)))).to_dict(orient="records")
    # NaN -> None for valid JSON
    clean = json.loads(pd.DataFrame(records).where(pd.notna(pd.DataFrame(records)), None).to_json(orient="records"))
    return {"count": len(clean), "opportunities": clean}


@app.get("/stock/{ticker}", dependencies=[Depends(require_api_key)])
def get_stock(ticker: str) -> dict:
    """Price, scoring, and news sentiment for one ticker."""
    symbol = ticker.strip().upper()

    df = _read_csv(FULL_SCAN)
    if df.empty or "symbol" not in df.columns:
        raise HTTPException(status_code=404, detail="No market scan available. Run the scanner first.")

    match = df[df["symbol"].astype(str).str.upper() == symbol]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found in today's scan.")

    row = match.iloc[0]

    def num(key):
        value = pd.to_numeric(row.get(key), errors="coerce")
        return None if pd.isna(value) else float(value)

    def text(key):
        value = row.get(key)
        return None if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)

    scoring = {
        "final_decision": text("final_decision"),
        "final_score": num("final_score"),
        "buy_probability": num("buy_probability"),
        "confidence_v3": num("confidence_v3"),
        "risk_permission": text("risk_permission"),
        "entry_timing_action": text("entry_timing_action"),
        "smart_money_score": num("smart_money_score"),
        "suggested_entry_price": num("suggested_entry_price"),
        "stop_loss": num("stop_loss"),
        "target_1": num("target_1"),
        "target_2": num("target_2"),
    }
    price = {
        "close": num("close"),
        "change_pct": num("change_pct"),
        "volume": num("volume"),
        "date": text("date"),
    }

    sentiment_cache = _read_json(SENTIMENT_CACHE)
    ticker_sentiment = (sentiment_cache.get("tickers", {}) or {}).get(symbol)

    return {
        "symbol": symbol,
        "company": text("company"),
        "sector": text("sector"),
        "price": price,
        "scoring": scoring,
        "news_sentiment": ticker_sentiment,  # None if no news matched this ticker
    }


@app.post("/query", dependencies=[Depends(require_api_key)])
def post_query(body: QueryRequest, stream: bool = False):
    """
    Ask the grounded assistant a question. Returns a full JSON answer by default;
    pass ?stream=true for a text/plain streamed response (for the future web/mobile
    clients). Assistant/billing/network failures return a clean JSON error.
    """
    try:
        client = get_client()
        system_prompt = build_system_prompt(load_context())
    except Exception as exc:
        # e.g. missing API key
        raise HTTPException(status_code=503, detail=f"Assistant unavailable: {exc}")

    messages = [{"role": "user", "content": body.question}]

    if stream:
        def generate():
            try:
                for chunk in stream_answer(client, system_prompt, messages):
                    yield chunk
            except Exception as exc:  # best-effort: stream ends with an error marker
                yield f"\n[error] {type(exc).__name__}: {exc}"

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    try:
        answer = "".join(stream_answer(client, system_prompt, messages))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant error: {type(exc).__name__}: {exc}")

    return {"question": body.question, "model": MODEL, "answer": answer}
