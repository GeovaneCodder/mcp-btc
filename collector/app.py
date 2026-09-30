import os, asyncio, json
from datetime import datetime, timezone
import httpx, redis, psycopg

REDIS_URL = os.getenv("REDIS_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "15"))
BASE = "https://api.binance.com"
FAPI = "https://fapi.binance.com"

r = redis.from_url(REDIS_URL, decode_responses=True)

async def fetch(client, path, params=None, futures=False):
    base = FAPI if futures else BASE
    resp = await client.get(base + path, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

async def collect():
    async with httpx.AsyncClient() as client:
        ticker, book, funding, oi = await asyncio.gather(
            fetch(client, "/api/v3/ticker/24hr", {"symbol": SYMBOL}),
            fetch(client, "/api/v3/depth", {"symbol": SYMBOL, "limit": 20}),
            fetch(client, "/fapi/v1/premiumIndex", {"symbol": SYMBOL}, True),
            fetch(client, "/fapi/v1/openInterest", {"symbol": SYMBOL}, True),
        )

        bid = float(book["bids"][0][0])
        ask = float(book["asks"][0][0])
        bid_volume = sum(float(p) * float(q) for p, q in book["bids"])
        ask_volume = sum(float(p) * float(q) for p, q in book["asks"])

        snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": SYMBOL,
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

        payload = json.dumps(snapshot)
        r.set("btc:latest", payload)
        r.lpush("btc:snapshots", payload)
        r.ltrim("btc:snapshots", 0, 20000)

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

        r.publish("btc:updates", payload)
        print(payload, flush=True)

async def main():
    while True:
        try:
            await collect()
        except Exception as exc:
            print(f"collector error: {exc}", flush=True)
        await asyncio.sleep(INTERVAL)

asyncio.run(main())
