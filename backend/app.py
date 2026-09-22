import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from core.market_data import market_data
from core.indicators import technical_engine
from core.smc import smc_engine
from core.sentiment import sentiment_aggregator
from core.signal_engine import signal_engine
from core.ai_vision import ai_vision
from core.news_engine import news_engine
from core.performance_tracker import tracker
from core.execution_engine import execution_engine

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="XAUUSD MT5 AI Trader API", version="2.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def telegram_webapp_middleware(request, call_next):
    is_head = request.method == "HEAD"
    if is_head:
        request.scope["method"] = "GET"

    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *;"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# Static files for Telegram Mini App
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "message": "XAUUSD AI Pro Trader Server is running"}

@app.get("/api/live")
async def get_live():
    return market_data.get_live_quote()

@app.get("/api/candles")
async def get_candles(timeframe: str = Query("M15"), count: int = Query(50)):
    return market_data.get_candles(timeframe=timeframe, count=count)

@app.get("/api/signals")
async def get_signals(timeframe: str = Query("M15")):
    return signal_engine.generate_signal(timeframe=timeframe)

@app.get("/api/scalp")
async def get_scalp():
    sig = signal_engine.generate_signal(timeframe="M5")
    return sig.get("scalp_setup", {})

@app.get("/api/news")
async def get_news():
    return news_engine.get_news_summary()

@app.get("/api/indicators")
async def get_indicators(timeframe: str = Query("M15")):
    candles = market_data.get_candles(timeframe=timeframe, count=60)
    tech = technical_engine.analyze_market(candles)
    smc = smc_engine.analyze_smc(candles)
    tech["smc"] = smc
    return tech

@app.get("/api/sentiment")
async def get_sentiment():
    return sentiment_aggregator.get_market_sentiment()

@app.get("/api/stats")
async def get_stats():
    return tracker.get_statistics()

class ExecuteOrderRequest(BaseModel):
    direction: str
    volume: Optional[float] = None
    risk_pct: Optional[float] = 2.0
    sl: Optional[float] = None
    tp: Optional[float] = None

@app.post("/api/execute")
async def execute_order(req: ExecuteOrderRequest):
    result = execution_engine.execute_trade(
        direction=req.direction,
        volume=req.volume,
        risk_pct=req.risk_pct,
        sl=req.sl,
        tp=req.tp
    )
    return result

@app.get("/api/positions")
async def get_positions():
    return execution_engine.get_open_positions()

@app.get("/api/account/status")
async def get_account_status():
    return market_data.get_account_info()

class LoginAccountRequest(BaseModel):
    login: int
    password: str
    server: str

@app.post("/api/account/login")
async def login_broker_account(req: LoginAccountRequest):
    res = market_data.login_account(login=req.login, password=req.password, server=req.server)
    return res

@app.post("/api/analyze-photo")
async def analyze_photo(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        analysis = ai_vision.analyze_chart_image(contents, filename=file.filename or "chart.jpg")
        return JSONResponse(content=analysis)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run(app, host=HOST, port=PORT)
