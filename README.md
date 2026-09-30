# MCP Bitcoin — simples e completo

Este projeto coleta dados do Bitcoin e entrega tudo para um LLM através de MCP.

A ideia é simples:

**fontes de dados → collector → Redis/PostgreSQL → MCP → LLM**

## O que o MCP entrega

### Mercado
- **Preço atual** — quanto 1 BTC vale agora.
- **Volume** — quanto foi negociado nas últimas 24 horas.
- **Order book** — ordens de compra e venda próximas do preço.
- **Spread** — diferença entre a melhor compra e a melhor venda.
- **Funding rate** — custo periódico entre posições compradas e vendidas em futuros.
- **Open interest** — quantidade de contratos futuros ainda abertos.
- **Liquidações** — posições de futuros encerradas à força.

### Volatilidade
Mede o quanto o preço está variando. Quanto maior, maior a oscilação recente.

### Opções
O projeto consulta a Deribit para obter calls, puts, open interest, volume e volatilidade implícita (IV).

### Grandes carteiras
Com **Glassnode** ou **Whale Alert**, o MCP pode acompanhar grandes movimentações de BTC.

### Entrada e saída das exchanges
Com **Glassnode**: BTC entrando, BTC saindo e saldo líquido das exchanges.

### Dados on-chain
Com **mempool.space**: taxas recomendadas, situação do mempool e hashrate da rede.

### Notícias
Notícias recentes sobre Bitcoin são coletadas via Google News RSS.

### Sentimento das redes sociais
Com **LunarCrush**: sentimento, volume social, interações e atividade agregada de redes como X, Reddit e YouTube.

### Correlação
O MCP calcula a correlação do BTC com ETH, S&P 500, Nasdaq e Dólar (DXY), usando retornos diários dos últimos 30 dias.

## Ferramenta principal do MCP

A ferramenta mais simples para usar com um LLM é **get_btc_market_data**. Ela retorna todas as informações em um único objeto.

Também existem:
- **get_btc_market_snapshot** — somente os números principais.
- **get_btc_history** — histórico dos snapshots.
- **get_btc_features** — indicadores simples.
- **predict_btc_4h** — baseline estatístico de 4 horas.

## Subir com Docker

    docker compose up --build

Depois:
- MCP: http://localhost:8000/mcp
- API de previsão: http://localhost:8001
- Snapshot: http://localhost:8001/snapshot
- Previsão: http://localhost:8001/predict/4h

## Chaves opcionais

O projeto funciona sem chaves para os dados públicos principais.

Crie um arquivo `.env` com:

    GLASSNODE_API_KEY=
    LUNARCRUSH_API_KEY=
    WHALE_ALERT_API_KEY=

Depois execute:

    docker compose up --build

Se uma chave não estiver configurada, o MCP informa **não configurado** em vez de quebrar o sistema.

## Para testar

    curl http://localhost:8001/snapshot
    curl http://localhost:8001/predict/4h

## Importante

Este projeto é **educacional**. Os dados servem para análise e alimentação de um LLM. A previsão de 4 horas é apenas um baseline estatístico e **não é uma previsão financeira validada nem recomendação de compra ou venda**.

## Fontes

- Binance — mercado, order book, funding, open interest e liquidações.
- Deribit — opções.
- mempool.space — dados da rede Bitcoin.
- Google News — notícias.
- LunarCrush — sentimento social, quando configurado.
- Glassnode — métricas on-chain, fluxo de exchanges e baleias, quando configurado.
- Whale Alert — grandes transações, quando configurado.
- Yahoo Finance — séries usadas para correlação com ETH, S&P 500, Nasdaq e DXY.