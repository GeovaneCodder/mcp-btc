# BTC MCP + Docker

MVP técnico para fornecer dados de BTC a um LLM via MCP e exibir um dashboard web reativo.

## Arquitetura

Binance REST
   ↓
collector
   ↓
Redis + PostgreSQL
   ├──→ predictor
   ├──→ MCP Server
   └──→ dashboard (WebSocket)

O collector publica cada snapshot no canal Redis `btc:updates`. O backend FastAPI do dashboard assina esse canal e entrega os dados ao Vue via WebSocket.

## Dashboard

Stack:
- Vue 3 + TypeScript + Vite
- Pinia
- FastAPI
- Redis Pub/Sub + WebSocket
- Docker

Subir tudo:

```bash
docker compose up --build
```

Dashboard: http://localhost:8080

MCP: http://localhost:8000/mcp
Prediction API: http://localhost:8001
Prediction: http://localhost:8001/predict/4h
Snapshot: http://localhost:8001/snapshot

## Ferramentas MCP

- `get_btc_market_snapshot`
- `get_btc_history`
- `get_btc_features`
- `predict_btc_4h`

## Importante

Este é um MVP técnico/educacional. O modelo de previsão é somente um baseline de momentum e não foi validado para trading. O dashboard não executa ordens.

O order book atualmente representa top-of-book e liquidez agregada; os níveis individuais ainda não são persistidos para exibição de profundidade.

## Próximos passos

1. WebSockets nativos para trades/order book no collector.
2. Dados reais de liquidação.
3. Histórico de Open Interest e Funding.
4. Bybit/Coinbase.
5. Dados on-chain.
6. Opções e IV.
7. Notícias e sentimento.
8. Features com janelas temporais.
9. XGBoost/LightGBM.
10. Backtesting walk-forward.
11. Calibração probabilística.
12. Monitoramento de drift.
