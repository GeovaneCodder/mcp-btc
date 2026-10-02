import asyncio
import json
import math
import os
import statistics
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import psycopg
import redis


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://btc:btc@postgres:5432/btc_ai")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "60"))

BINANCE = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
DERIBIT = "https://www.deribit.com/api/v2"
MEMPOOL = "https://mempool.space/api"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
REDDIT = "https://www.reddit.com"

r = redis.from_url(REDIS_URL, decode_responses=True)

async def fetch(client, path, params=None, futures=False):
    base = FAPI if futures else BASE
    resp = await client.get(base + path, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

async def collect():
    async with httpx.AsyncClient() as client:
        ticker, book, funding, oi, liquidations = await asyncio.gather(
            get(client, f"{BINANCE}/api/v3/ticker/24hr", {"symbol": SYMBOL}),
            get(client, f"{BINANCE}/api/v3/depth", {"symbol": SYMBOL, "limit": 10}),
            get(client, f"{BINANCE_FUTURES}/fapi/v1/premiumIndex", {"symbol": SYMBOL}),
            get(client, f"{BINANCE_FUTURES}/fapi/v1/openInterest", {"symbol": SYMBOL}),
            get(client, f"{BINANCE_FUTURES}/fapi/v1/allForceOrders", {"symbol": SYMBOL, "limit": 100}),
        )

        if not ticker or not book:
            raise RuntimeError("Binance não retornou os dados básicos do mercado.")

        bid = float(book["bids"][0][0])
        ask = float(book["asks"][0][0])
        bid_volume = sum(float(p) * float(q) for p, q in book["bids"])
        ask_volume = sum(float(p) * float(q) for p, q in book["asks"])

        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "timestamp": timestamp,
            "ts": timestamp,
            "symbol": SYMBOL,

            # Campos simples para o predictor.
            "price": float(ticker["lastPrice"]),
            "volume_24h": float(ticker["quoteVolume"]),
            "bid": bid,
            "ask": ask,
            "spread": ask - bid,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "funding_rate": float(funding["lastFundingRate"]),
            "open_interest": float(oi["openInterest"]),
            "liquidation_long": 0.0,
            "liquidation_short": 0.0
        }

        r.set("btc:latest", json.dumps(snapshot))
        r.lpush("btc:snapshots", json.dumps(snapshot))
        r.ltrim("btc:snapshots", 0, 20000)

        # Publica o snapshot para o dashboard em tempo real.
        # O WebSocket do dashboard escuta este canal e atualiza a interface
        # a cada nova coleta, sem depender de recarregar a página.
        r.publish("btc:updates", payload)

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("""
                INSERT INTO market_snapshots
                (ts,symbol,price,volume_24h,bid,ask,spread,bid_volume,
                 ask_volume,funding_rate,open_interest,liquidation_long,
                 liquidation_short)
                VALUES (%(ts)s,%(symbol)s,%(price)s,%(volume_24h)s,%(bid)s,
                        %(ask)s,%(spread)s,%(bid_volume)s,%(ask_volume)s,
                        %(funding_rate)s,%(open_interest)s,
                        %(liquidation_long)s,%(liquidation_short)s)
            """, snapshot)
            conn.commit()

        print(json.dumps(snapshot), flush=True)

async def main():
    while True:
        try:
            await collect()
        except Exception as exc:
            print(f"collector error: {exc}", flush=True)
        await asyncio.sleep(INTERVAL)


asyncio.run(main())
