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
KRAKEN = "https://api.kraken.com/0/public"
KRAKEN_FUTURES = "https://futures.kraken.com/derivatives/api/v3"
KRAKEN_SPOT_PAIR = "XBTUSD"
KRAKEN_FUTURES_SYMBOL = "PI_XBTUSD"
DERIBIT = "https://www.deribit.com/api/v2"
MEMPOOL = "https://mempool.space/api"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
REDDIT = "https://www.reddit.com"

r = redis.from_url(REDIS_URL, decode_responses=True)


async def get(client, url, params=None, headers=None):
    try:
        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=15,
            follow_redirects=True,
        )
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
    prices = [json.loads(x)["price"] for x in raw if json.loads(x).get("price")]
    if len(prices) < 20:
        return {
            "status": "aguardando_historico",
            "explicacao": "A volatilidade aparece depois de acumular alguns minutos de preços.",
        }

    prices.reverse()
    returns = [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]
    if len(returns) < 2:
        return {"status": "aguardando_historico"}

    value = statistics.pstdev(returns) * math.sqrt(len(returns)) * 100
    return {
        "status": "ok",
        "periodo": "aproximadamente 1 hora",
        "volatilidade_percentual": round(value, 4),
        "explicacao": "Quanto maior o número, maior a oscilação recente do preço.",
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

    def total(values, field):
        return sum(float(x.get(field) or 0) for x in values)

    def avg_iv(values):
        ivs = [float(x["mark_iv"]) for x in values if x.get("mark_iv") is not None]
        return round(statistics.mean(ivs), 2) if ivs else None

    return status(
        {
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
            "explicacao": "Opções mostram posicionamento do mercado para preços futuros. IV é a volatilidade implícita.",
        },
        "Deribit",
    )


async def get_onchain(client):
    fees, mempool, hashrate, recent = await asyncio.gather(
        get(client, f"{MEMPOOL}/v1/fees/recommended"),
        get(client, f"{MEMPOOL}/mempool"),
        get(client, f"{MEMPOOL}/v1/mining/hashrate/1m"),
        get(client, f"{MEMPOOL}/mempool/recent"),
    )
    return {
        "status": "ok" if any(x is not None for x in [fees, mempool, hashrate]) else "indisponivel",
        "fonte": "mempool.space",
        "taxas_recomendadas": fees,
        "mempool": mempool,
        "hashrate": hashrate,
        "transacoes_recentes": recent,
        "explicacao": "Dados públicos diretamente relacionados à atividade da rede Bitcoin.",
    }


async def get_news(client):
    url = "https://news.google.com/rss/search?q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    try:
        response = await client.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        news = []
        for item in root.findall("./channel/item")[:10]:
            news.append(
                {
                    "titulo": item.findtext("title"),
                    "link": item.findtext("link"),
                    "data": item.findtext("pubDate"),
                    "fonte": item.findtext("source"),
                }
            )
        return status(news, "Google News RSS")
    except Exception as exc:
        print(f"news error: {exc}", flush=True)
        return status(None, "Google News RSS")


def sentiment_score(text):
    positive = {
        "alta", "subiu", "sobe", "ganho", "ganhos", "otimismo", "otimista",
        "bullish", "positivo", "positiva", "recorde", "rali", "rally",
        "compra", "compras", "adocao", "adoção", "crescimento", "forte",
    }
    negative = {
        "queda", "caiu", "cai", "perda", "perdas", "medo", "pessimismo",
        "bearish", "negativo", "negativa", "crise", "venda", "vendas",
        "recuo", "colapso", "risco", "fraco", "fraqueza",
    }
    words = set(text.lower().replace(",", " ").replace(".", " ").split())
    score = len(words & positive) - len(words & negative)
    return score


async def get_social_sentiment(client):
    data = await get(
        client,
        f"{REDDIT}/r/Bitcoin/search.json",
        {
            "q": "bitcoin",
            "restrict_sr": "on",
            "sort": "new",
            "limit": 50,
            "raw_json": 1,
        },
        headers={"User-Agent": "btc-mcp/1.0 public-market-data"},
    )
    if not data:
        return {
            "status": "indisponivel",
            "fonte": "Reddit público",
            "explicacao": "Não foi possível consultar as publicações públicas do Reddit agora.",
        }

    posts = []
    scores = []
    for child in data.get("data", {}).get("children", []):
        item = child.get("data", {})
        title = item.get("title", "")
        body = item.get("selftext", "")
        text = f"{title} {body}".strip()
        if not text:
            continue
        score = sentiment_score(text)
        scores.append(score)
        posts.append(
            {
                "titulo": title,
                "pontuacao_reddit": item.get("score", 0),
                "comentarios": item.get("num_comments", 0),
                "sentimento_textual": "positivo" if score > 0 else "negativo" if score < 0 else "neutro",
            }
        )

    total = sum(scores)
    return {
        "status": "ok",
        "fonte": "Reddit público",
        "publicacoes_analisadas": len(posts),
        "sentimento_textual": "positivo" if total > 0 else "negativo" if total < 0 else "neutro",
        "pontuacao": total,
        "publicacoes": posts[:20],
        "explicacao": "É uma leitura simples do texto de publicações públicas, não um indicador profissional de sentimento.",
    }


async def get_whales(client):
    data = await get(client, f"{MEMPOOL}/mempool/recent")
    if not data:
        return {
            "status": "indisponivel",
            "fonte": "mempool.space",
            "explicacao": "Não foi possível consultar as transações recentes.",
        }

    transactions = []
    for tx in data:
        value_btc = float(tx.get("value", 0)) / 100_000_000
        if value_btc >= 10:
            transactions.append(
                {
                    "txid": tx.get("txid"),
                    "valor_btc": round(value_btc, 8),
                    "taxa_sat": tx.get("fee"),
                    "vsize": tx.get("vsize"),
                }
            )

    transactions.sort(key=lambda x: x["valor_btc"], reverse=True)
    return {
        "status": "ok",
        "fonte": "mempool.space",
        "transacoes_grandes_no_mempool": transactions,
        "explicacao": "São grandes transações públicas observadas no mempool. Sem uma base paga de etiquetas, não afirmamos que uma carteira pertence a uma baleia ou exchange.",
    }


async def get_exchange_flows(client):
    return {
        "status": "nao_disponivel",
        "fonte": "dados públicos Bitcoin",
        "entrada_24h_btc": None,
        "saida_24h_btc": None,
        "saldo_liquido_24h_btc": None,
        "explicacao": "Fluxo de BTC para dentro e fora de exchanges exige identificar endereços de exchanges. Para não usar API paga ou inventar etiquetas, o projeto não estima esse valor.",
    }


async def yahoo_series(client, symbol, period_days=30):
    data = await get(
        client,
        f"{YAHOO}/{quote(symbol, safe='')}",
        {"range": f"{period_days}d", "interval": "1d", "events": "history"},
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
        other = returns(await yahoo_series(client, symbol))
        n = min(len(btc_returns), len(other))
        if n < 5:
            result[name] = None
            continue
        a, b = btc_returns[-n:], other[-n:]
        mean_a, mean_b = statistics.mean(a), statistics.mean(b)
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
        den = math.sqrt(
            sum((x - mean_a) ** 2 for x in a)
            * sum((y - mean_b) ** 2 for y in b)
        )
        result[name] = round(cov / den, 4) if den else 0

    return {
        "status": "ok" if result else "indisponivel",
        "fonte": "Yahoo Finance público",
        "periodo": "últimos 30 dias",
        "correlacao_com_BTC": result,
        "explicacao": "1 = movimentos muito parecidos; -1 = movimentos opostos; 0 = pouca relação.",
    }


async def get_kraken_core(client):
    ticker, book, futures = await asyncio.gather(
        get(client, f"{KRAKEN}/Ticker", {"pair": KRAKEN_SPOT_PAIR}),
        get(client, f"{KRAKEN}/Depth", {"pair": KRAKEN_SPOT_PAIR, "count": 10}),
        get(client, f"{KRAKEN_FUTURES}/tickers"),
    )

    spot = (ticker or {}).get("result", {}).get("XXBTZUSD")
    depth = (book or {}).get("result", {}).get("XXBTZUSD")
    futures_items = (futures or {}).get("tickers", [])
    future = next(
        (item for item in futures_items if item.get("symbol") == KRAKEN_FUTURES_SYMBOL),
        None,
    )

    if not spot or not depth or not depth.get("bids") or not depth.get("asks"):
        return None

    bids = [[float(price), float(qty)] for price, qty, *_ in depth["bids"][:10]]
    asks = [[float(price), float(qty)] for price, qty, *_ in depth["asks"][:10]]
    bid = bids[0][0]
    ask = asks[0][0]
    last = float(spot["c"][0])
    volume_base = float(spot["v"][1])
    volume_quote = volume_base * last
    open_price = float(spot["o"])
    change_pct = ((last - open_price) / open_price * 100) if open_price else 0

    return {
        "ticker": {
            "lastPrice": last,
            "quoteVolume": volume_quote,
            "priceChangePercent": change_pct,
            "highPrice": float(spot["h"][1]),
            "lowPrice": float(spot["l"][1]),
        },
        "book": {"bids": bids, "asks": asks},
        "funding": float((future or {}).get("fundingRate", 0) or 0),
        "open_interest": float((future or {}).get("openInterest", 0) or 0),
        "liquidations": None,
        "source": "Kraken / Kraken Futures",
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

        source = "Binance / Binance Futures"
        if not ticker or not book:
            kraken = await get_kraken_core(client)
            if not kraken:
                raise RuntimeError("Binance e Kraken não retornaram os dados básicos do mercado.")
            ticker = kraken["ticker"]
            book = kraken["book"]
            funding = {"lastFundingRate": kraken["funding"]}
            oi = {"openInterest": kraken["open_interest"]}
            liquidations = kraken["liquidations"]
            source = kraken["source"]

        bid = float(book["bids"][0][0])
        ask = float(book["asks"][0][0])
        bid_volume = sum(float(price) * float(qty) for price, qty in book["bids"])
        ask_volume = sum(float(price) * float(qty) for price, qty in book["asks"])

        liquidations = liquidations or []
        long_liq = sum(
            float(x.get("origQty", 0)) * float(x.get("price", 0))
            for x in liquidations if x.get("side") == "SELL"
        )
        short_liq = sum(
            float(x.get("origQty", 0)) * float(x.get("price", 0))
            for x in liquidations if x.get("side") == "BUY"
        )

        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "timestamp": timestamp,
            "ts": timestamp,
            "symbol": SYMBOL,
            "source": source,
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
                    "fonte": source,
                },
            },
        }

        previous = r.get("btc:latest")
        previous_data = json.loads(previous) if previous else {}
        refresh_extra = time.time() - float(r.get("btc:extras_ts") or 0) >= 300
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
            for name, value in zip(names, extra):
                snapshot[name] = (
                    value
                    if not isinstance(value, Exception)
                    else {"status": "erro", "mensagem": str(value)}
                )
            r.set("btc:extras_ts", str(time.time()))
        else:
            for name in names:
                if name in previous_data:
                    snapshot[name] = previous_data[name]

        snapshot["volatilidade"] = calculate_volatility()

        payload = json.dumps(snapshot, ensure_ascii=False)
        r.set("btc:latest", payload)
        r.lpush("btc:snapshots", payload)
        r.ltrim("btc:snapshots", 0, 20000)
        r.publish("btc:updates", payload)

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                """
                INSERT INTO market_snapshots
                    (ts, symbol, price, volume_24h, spread, funding_rate, open_interest, data)
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
                    payload,
                ),
            )
            conn.commit()

        print(payload, flush=True)


async def main():
    while True:
        try:
            await collect()
        except Exception as exc:
            print(f"collector error: {exc}", flush=True)
        await asyncio.sleep(INTERVAL)


asyncio.run(main())
