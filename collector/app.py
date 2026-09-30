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
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "15"))

BINANCE = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
DERIBIT = "https://www.deribit.com/api/v2"
MEMPOOL = "https://mempool.space/api"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"

r = redis.from_url(REDIS_URL, decode_responses=True)

GLASSNODE_API_KEY = os.getenv("GLASSNODE_API_KEY", "")
LUNARCRUSH_API_KEY = os.getenv("LUNARCRUSH_API_KEY", "")
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")


async def get(client, url, params=None, headers=None):
    try:
        response = await client.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"source error {url}: {exc}", flush=True)
        return None


def status(data, source):
    if data is None:
        return {"status": "indisponivel", "fonte": source}
    return {"status": "ok", "fonte": source, "dados": data}


def calculate_volatility():
    raw = r.lrange("btc:snapshots", 0, 239)
    prices = [json.loads(x)["price"] for x in raw]
    if len(prices) < 20:
        return {
            "status": "aguardando_historico",
            "explicacao": "A volatilidade aparece depois de acumular alguns minutos de preços."
        }

    prices = list(reversed(prices))
    returns = [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]

    if len(returns) < 2:
        return {"status": "aguardando_historico"}

    # Coleta a cada 15s: 240 pontos ≈ 1 hora.
    value = statistics.pstdev(returns) * math.sqrt(len(returns)) * 100

    return {
        "status": "ok",
        "periodo": "aproximadamente 1 hora",
        "volatilidade_percentual": round(value, 4),
        "explicacao": "Quanto maior o número, maior a variação recente do preço."
    }


async def get_options(client):
    data = await get(
        client,
        f"{DERIBIT}/public/get_book_summary_by_currency",
        {"currency": "BTC", "kind": "option"},
    )
    if not data or "result" not in data:
        return status(None, "Deribit")

    items = data["result"]
    calls = [x for x in items if "-C" in x.get("instrument_name", "")]
    puts = [x for x in items if "-P" in x.get("instrument_name", "")]

    def total(items, field):
        return sum(float(x.get(field) or 0) for x in items)

    def avg_iv(items):
        values = [float(x["mark_iv"]) for x in items if x.get("mark_iv") is not None]
        return round(statistics.mean(values), 2) if values else None

    result = {
        "quantidade_instrumentos": len(items),
        "calls": {
            "quantidade": len(calls),
            "open_interest": total(calls, "open_interest"),
            "volume_24h": total(calls, "volume_usd"),
            "iv_media": avg_iv(calls),
        },
        "puts": {
            "quantidade": len(puts),
            "open_interest": total(puts, "open_interest"),
            "volume_24h": total(puts, "volume_usd"),
            "iv_media": avg_iv(puts),
        },
        "explicacao": "Opções mostram como o mercado está se posicionando para preços futuros. IV é a volatilidade implícita.",
    }
    return status(result, "Deribit")


async def get_onchain(client):
    fees, mempool, hashrate = await asyncio.gather(
        get(client, f"{MEMPOOL}/v1/fees/recommended"),
        get(client, f"{MEMPOOL}/mempool"),
        get(client, f"{MEMPOOL}/v1/mining/hashrate/1m"),
    )

    return {
        "status": "ok" if any(x is not None for x in [fees, mempool, hashrate]) else "indisponivel",
        "fonte": "mempool.space",
        "taxas_recomendadas": fees,
        "mempool": mempool,
        "hashrate": hashrate,
        "explicacao": "Dados diretamente relacionados à atividade da rede Bitcoin."
    }


async def get_news(client):
    url = (
        "https://news.google.com/rss/search?"
        "q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        news = []
        for item in root.findall("./channel/item")[:10]:
            news.append({
                "titulo": item.findtext("title"),
                "link": item.findtext("link"),
                "data": item.findtext("pubDate"),
                "fonte": item.findtext("source"),
            })
        return status(news, "Google News RSS")
    except Exception as exc:
        print(f"news error: {exc}", flush=True)
        return status(None, "Google News RSS")


async def get_social_sentiment(client):
    if not LUNARCRUSH_API_KEY:
        return {
            "status": "nao_configurado",
            "fonte": "LunarCrush",
            "explicacao": "Defina LUNARCRUSH_API_KEY para ativar sentimento de redes sociais."
        }

    data = await get(
        client,
        "https://lunarcrush.com/api4/public/topic/bitcoin/v1",
        headers={"Authorization": f"Bearer {LUNARCRUSH_API_KEY}"},
    )
    if not data:
        return status(None, "LunarCrush")

    return status(data.get("data", data), "LunarCrush")


async def get_whales(client):
    result = {}

    if GLASSNODE_API_KEY:
        headers = {"X-Api-Key": GLASSNODE_API_KEY}
        whale_in, whale_out = await asyncio.gather(
            get(
                client,
                "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_whales_to_exchanges_sum",
                {"a": "BTC", "i": "24h", "f": "json"},
                headers,
            ),
            get(
                client,
                "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_exchanges_to_whales_sum",
                {"a": "BTC", "i": "24h", "f": "json"},
                headers,
            ),
        )
        result["glassnode"] = {
            "baleias_para_exchanges": whale_in[-1] if whale_in else None,
            "exchanges_para_baleias": whale_out[-1] if whale_out else None,
            "explicacao": "Glassnode considera baleias como entidades que possuem pelo menos 1.000 BTC."
        }

    if WHALE_ALERT_API_KEY:
        now = int(time.time())
        data = await get(
            client,
            "https://leviathan.whale-alert.io/bitcoin/transactions",
            {
                "api_key": WHALE_ALERT_API_KEY,
                "symbol": "btc",
                "min_amount": 100,
                "limit": 20,
                "order": "desc",
                "start_height": 0,
            },
        )
        if data:
            result["whale_alert"] = data

    if not result:
        return {
            "status": "nao_configurado",
            "explicacao": "Defina GLASSNODE_API_KEY e/ou WHALE_ALERT_API_KEY para acompanhar grandes movimentações."
        }

    return status(result, "Glassnode / Whale Alert")


async def get_exchange_flows(client):
    if not GLASSNODE_API_KEY:
        return {
            "status": "nao_configurado",
            "fonte": "Glassnode",
            "explicacao": "Defina GLASSNODE_API_KEY para receber entrada, saída e saldo líquido de BTC nas exchanges."
        }

    headers = {"X-Api-Key": GLASSNODE_API_KEY}
    inflow, outflow, netflow = await asyncio.gather(
        get(
            client,
            "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_to_exchanges_sum",
            {"a": "BTC", "i": "24h", "f": "json"},
            headers,
        ),
        get(
            client,
            "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_from_exchanges_sum",
            {"a": "BTC", "i": "24h", "f": "json"},
            headers,
        ),
        get(
            client,
            "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_exchanges_net",
            {"a": "BTC", "i": "24h", "f": "json"},
            headers,
        ),
    )

    return {
        "status": "ok",
        "fonte": "Glassnode",
        "entrada_24h_btc": inflow[-1] if inflow else None,
        "saida_24h_btc": outflow[-1] if outflow else None,
        "saldo_liquido_24h_btc": netflow[-1] if netflow else None,
        "explicacao": "Saldo positivo significa mais BTC entrando nas exchanges do que saindo."
    }


async def yahoo_series(client, symbol, period_days=30):
    data = await get(
        client,
        f"{YAHOO}/{quote(symbol, safe='')}",
        {
            "range": f"{period_days}d",
            "interval": "1d",
            "events": "history",
        },
    )
    if not data:
        return []

    try:
        return [
            float(x)
            for x in data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            if x is not None
        ]
    except (KeyError, IndexError, TypeError):
        return []


async def get_correlations(client):
    symbols = {
        "ETH": "ETH-USD",
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dólar (DXY)": "DX-Y.NYB",
    }
    btc = await yahoo_series(client, "BTC-USD")
    result = {}

    def returns(values):
        return [
            math.log(values[i] / values[i - 1])
            for i in range(1, len(values))
            if values[i - 1] > 0 and values[i] > 0
        ]

    btc_returns = returns(btc)

    for name, symbol in symbols.items():
        values = await yahoo_series(client, symbol)
        other = returns(values)
        n = min(len(btc_returns), len(other))
        if n < 5:
            result[name] = None
            continue
        a = btc_returns[-n:]
        b = other[-n:]
        mean_a = statistics.mean(a)
        mean_b = statistics.mean(b)
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
        den = math.sqrt(
            sum((x - mean_a) ** 2 for x in a)
            * sum((y - mean_b) ** 2 for y in b)
        )
        result[name] = round(cov / den, 4) if den else 0

    return {
        "status": "ok" if result else "indisponivel",
        "periodo": "últimos 30 dias",
        "correlacao_com_BTC": result,
        "explicacao": "1 = movimento muito parecido; -1 = movimento oposto; 0 = pouca relação."
    }


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

        bid_volume = sum(float(price) * float(qty) for price, qty in book["bids"])
        ask_volume = sum(float(price) * float(qty) for price, qty in book["asks"])

        liquidations = liquidations or []
        long_liq = sum(
            float(x.get("origQty", 0)) * float(x.get("price", 0))
            for x in liquidations
            if x.get("side") == "SELL"
        )
        short_liq = sum(
            float(x.get("origQty", 0)) * float(x.get("price", 0))
            for x in liquidations
            if x.get("side") == "BUY"
        )

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": SYMBOL,

            # Campos simples para o predictor.
            "price": float(ticker["lastPrice"]),
            "volume_24h": float(ticker["quoteVolume"]),
            "bid": bid,
            "ask": ask,
            "spread": ask - bid,
            "funding_rate": float((funding or {}).get("lastFundingRate", 0)),
            "open_interest": float((oi or {}).get("openInterest", 0)),

            "mercado": {
                "preco_atual_usd": float(ticker["lastPrice"]),
                "variacao_24h_percentual": float(ticker["priceChangePercent"]),
                "volume_24h_usd": float(ticker["quoteVolume"]),
                "maxima_24h_usd": float(ticker["highPrice"]),
                "minima_24h_usd": float(ticker["lowPrice"]),
            },

            "order_book": {
                "melhor_compra": bid,
                "melhor_venda": ask,
                "spread_usd": ask - bid,
                "spread_percentual": ((ask - bid) / bid) * 100 if bid else 0,
                "compras": book["bids"],
                "vendas": book["asks"],
                "volume_compras_usd": bid_volume,
                "volume_vendas_usd": ask_volume,
            },

            "derivativos": {
                "funding_rate": float((funding or {}).get("lastFundingRate", 0)),
                "open_interest_btc": float((oi or {}).get("openInterest", 0)),
                "liquidacoes": {
                    "longs_usd": long_liq,
                    "shorts_usd": short_liq,
                    "quantidade_eventos": len(liquidations),
                },
            },
        }

        # Dados externos mais lentos são atualizados a cada 5 minutos.
        previous = r.get("btc:latest")
        previous_data = json.loads(previous) if previous else {}
        refresh_extra = time.time() - float(r.get("btc:extras_ts") or 0) >= 300
        extra = await asyncio.gather(
            get_options(client),
            get_onchain(client),
            get_news(client),
            get_social_sentiment(client),
            get_whales(client),
            get_exchange_flows(client),
            get_correlations(client),
            return_exceptions=True,
        )

        names = [
            "opcoes",
            "on_chain",
            "noticias",
            "sentimento_social",
            "grandes_carteiras",
            "fluxo_exchanges",
            "correlacoes",
        ]

        if refresh_extra:
            for name, value in zip(names, extra):
                snapshot[name] = value if not isinstance(value, Exception) else {"status": "erro", "mensagem": str(value)}
            r.set("btc:extras_ts", str(time.time()))
        else:
            for name in names:
                if name in previous_data:
                    snapshot[name] = previous_data[name]

        snapshot["volatilidade"] = calculate_volatility()

        r.set("btc:latest", json.dumps(snapshot, ensure_ascii=False))
        r.lpush("btc:snapshots", json.dumps(snapshot, ensure_ascii=False))
        r.ltrim("btc:snapshots", 0, 20000)

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                """
                INSERT INTO market_snapshots (ts, symbol, price, volume_24h, spread,
                                              funding_rate, open_interest, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    snapshot["timestamp"],
                    SYMBOL,
                    snapshot["price"],
                    snapshot["volume_24h"],
                    snapshot["spread"],
                    snapshot["funding_rate"],
                    snapshot["open_interest"],
                    json.dumps(snapshot, ensure_ascii=False),
                ),
            )
            conn.commit()

        print(json.dumps(snapshot, ensure_ascii=False), flush=True)


async def main():
    while True:
        try:
            await collect()
        except Exception as exc:
            print(f"collector error: {exc}", flush=True)
        await asyncio.sleep(INTERVAL)


asyncio.run(main())
