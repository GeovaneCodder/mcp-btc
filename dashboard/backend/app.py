import asyncio
import json
import os
from pathlib import Path

import httpx
import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PREDICTOR_URL = os.getenv("PREDICTOR_URL", "http://predictor:8001")
r = redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="BTC Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/snapshot")
def snapshot():
    raw = r.get("btc:latest")
    return json.loads(raw) if raw else {"status": "no_data"}

@app.get("/api/history")
def history(limit: int = 200):
    limit = max(1, min(limit, 1000))
    return [json.loads(x) for x in r.lrange("btc:snapshots", 0, limit - 1)][::-1]

@app.get("/api/predict/4h")
async def predict():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PREDICTOR_URL}/predict/4h", timeout=15)
        response.raise_for_status()
        return response.json()

@app.websocket("/ws/market")
async def market_socket(websocket: WebSocket):
    await websocket.accept()
    pubsub = r.pubsub()
    pubsub.subscribe("btc:updates")
    try:
        while True:
            message = await asyncio.to_thread(pubsub.get_message, True, 1.0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        pubsub.close()

dist = Path(__file__).resolve().parents[1] / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

@app.get("/{path:path}")
async def frontend(path: str):
    index = dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Dashboard frontend not built"}
