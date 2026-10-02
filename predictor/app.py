import os, json
from datetime import datetime, timezone
import numpy as np
import redis, psycopg
from fastapi import FastAPI

app = FastAPI(title="BTC Prediction API")
r = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
DB = os.getenv("DATABASE_URL")
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "60"))

def snapshots(limit=2000):
    raw = r.lrange("btc:snapshots", 0, limit-1)
    return [json.loads(x) for x in raw]

def predict_4h():
    data = snapshots()
    if len(data) < 30:
        return {
            "status": "insufficient_data",
            "message": "Aguardando histórico. O collector precisa acumular dados."
        }

    data = list(reversed(data))
    prices = np.array([x["price"] for x in data], dtype=float)

    # Baseline estatístico simples para o MVP.
    # Não é um modelo financeiro validado.
    returns = np.diff(np.log(prices))
    recent = returns[-min(100, len(returns)):]
    momentum = float(np.mean(recent))
    volatility = float(np.std(recent))

    last = float(prices[-1])
    # Horizonte aproximado de 4h usando o intervalo atual de coleta.
    steps = max(1, int((4 * 3600) / INTERVAL_SECONDS))
    expected_return = float(np.clip(momentum * steps, -0.10, 0.10))
    predicted = last * np.exp(expected_return)

    direction = "UP" if expected_return > 0.002 else "DOWN" if expected_return < -0.002 else "SIDEWAYS"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "horizon": "4h",
        "current_price": last,
        "predicted_price": round(predicted, 2),
        "predicted_return": round(expected_return, 6),
        "direction": direction,
        "volatility_per_sample": volatility,
        "samples": len(data),
        "model": "momentum_baseline",
        "warning": ""
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/snapshot")
def snapshot():
    raw = r.get("btc:latest")
    return json.loads(raw) if raw else {"status": "no_data"}

@app.get("/predict/4h")
def prediction():
    return predict_4h()
