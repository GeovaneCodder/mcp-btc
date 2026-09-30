import json
import os

import httpx
import redis
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("btc-market-mcp")
r = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
PREDICTOR = os.getenv("PREDICTOR_URL", "http://predictor:8001")


def latest():
    raw = r.get("btc:latest")
    return json.loads(raw) if raw else None


@mcp.tool()
def get_btc_market_data() -> dict:
    """Retorna TODOS os dados do Bitcoin em linguagem simples: preço, volume,
    order book, spread, funding, open interest, liquidações, volatilidade,
    opções, baleias, fluxo de exchanges, on-chain, notícias, sentimento social
    e correlações com ETH, S&P 500, Nasdaq e dólar."""
    return latest() or {
        "status": "sem_dados",
        "mensagem": "O collector ainda está buscando os primeiros dados."
    }


@mcp.tool()
def get_btc_market_snapshot() -> dict:
    """Retorna somente os principais números atuais do BTC."""
    data = latest()
    if not data:
        return {"status": "sem_dados"}

    return {
        "preco_atual_usd": data["mercado"]["preco_atual_usd"],
        "variacao_24h_percentual": data["mercado"]["variacao_24h_percentual"],
        "volume_24h_usd": data["mercado"]["volume_24h_usd"],
        "spread_usd": data["order_book"]["spread_usd"],
        "funding_rate": data["derivativos"]["funding_rate"],
        "open_interest_btc": data["derivativos"]["open_interest_btc"],
        "volatilidade": data["volatilidade"],
    }


@mcp.tool()
def get_btc_history(limit: int = 100) -> list:
    """Retorna os últimos snapshots do BTC."""
    limit = max(1, min(limit, 1000))
    raw = r.lrange("btc:snapshots", 0, limit - 1)
    return [json.loads(x) for x in raw]


@mcp.tool()
def get_btc_features() -> dict:
    """Retorna indicadores simples para análise."""
    data = latest()
    if not data:
        return {"status": "sem_dados"}

    book = data["order_book"]
    total = book["volume_compras_usd"] + book["volume_vendas_usd"]
    imbalance = (
        (book["volume_compras_usd"] - book["volume_vendas_usd"]) / total
        if total else 0
    )

    return {
        "preco_atual_usd": data["price"],
        "spread_usd": data["spread"],
        "spread_bps": (data["spread"] / data["price"]) * 10000,
        "forca_do_order_book": round(imbalance, 6),
        "funding_rate": data["funding_rate"],
        "open_interest_btc": data["open_interest"],
        "volatilidade": data["volatilidade"],
    }


@mcp.tool()
async def predict_btc_4h() -> dict:
    """Retorna o baseline estatístico de 4 horas do projeto.
    Não é recomendação financeira."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PREDICTOR}/predict/4h", timeout=15)
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
