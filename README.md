# BTC MCP + Docker

MVP de uma arquitetura para fornecer dados de BTC a um LLM via MCP.

## Arquitetura

Binance REST
   ↓
collector
   ↓
Redis + PostgreSQL
   ↓
predictor
   ↓
MCP Server
   ↓
LLM / agente

## Subir

```bash
docker compose up --build
```

Depois:

- MCP: http://localhost:8000/mcp
- Prediction API: http://localhost:8001
- Prediction: http://localhost:8001/predict/4h
- Snapshot: http://localhost:8001/snapshot

## Ferramentas MCP

- `get_btc_market_snapshot`
- `get_btc_history`
- `get_btc_features`
- `predict_btc_4h`

## Importante

Este é um MVP técnico/educacional. O modelo de previsão é somente um baseline de momentum e não foi validado para trading.

Para evoluir:

1. WebSockets para trades/order book.
2. Dados de liquidação.
3. Bybit/Coinbase.
4. Dados on-chain.
5. Open Interest histórico.
6. Opções e IV.
7. Notícias e sentimento.
8. Features com janelas temporais.
9. XGBoost/LightGBM.
10. Backtesting walk-forward.
11. Calibração probabilística.
12. Monitoramento de drift.

## Teste rápido

```bash
curl http://localhost:8001/snapshot
curl http://localhost:8001/predict/4h
```
