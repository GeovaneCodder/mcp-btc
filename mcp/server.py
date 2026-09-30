import os, json
import httpx, redis
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("btc-market-mcp")
r = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
PREDICTOR = os.getenv("PREDICTOR_URL", "http://predictor:8001")

@mcp.tool()
def get_btc_market_snapshot() -> dict:
    """Retorna o snapshot mais recente do mercado BTC/USDT."""
    raw = r.get("btc:latest")
    return json.loads(raw) if raw else {"status": "no_data"}

@mcp.tool()
def get_btc_history(limit: int = 100) -> list:
    """Retorna snapshots recentes do BTC."""
    limit = max(1, min(limit, 1000))
    raw = r.lrange("btc:snapshots", 0, limit - 1)
    return [json.loads(x) for x in raw]

@mcp.tool()
async def predict_btc_4h() -> dict:
    """Solicita ao serviço de previsão uma estimativa para as próximas 4 horas."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PREDICTOR}/predict/4h", timeout=15)
        response.raise_for_status()
        return response.json()

@mcp.tool()
def get_btc_features() -> dict:
    """Calcula indicadores básicos a partir do último snapshot."""
    raw = r.get("btc:latest")
    if not raw:
        return {"status": "no_data"}

    x = json.loads(raw)
    total = x["bid_volume"] + x["ask_volume"]
    imbalance = (
        (x["bid_volume"] - x["ask_volume"]) / total
        if total else 0
    )

    return {
        "price": x["price"],
        "spread": x["spread"],
        "spread_bps": (x["spread"] / x["price"]) * 10000,
        "order_book_imbalance": imbalance,
        "funding_rate": x["funding_rate"],
        "open_interest": x["open_interest"]
    }

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
