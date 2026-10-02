# MCP Bitcoin — 100% com fontes públicas e gratuitas

Este projeto coleta dados do Bitcoin e entrega tudo para um LLM através de MCP.

A ideia é simples:

**fontes públicas → collector → Redis/PostgreSQL → MCP → LLM**

## O projeto usa APIs pagas?

**Não.**

O collector não precisa de API key, cartão, assinatura ou conta paga.

As fontes usadas são públicas e gratuitas. Elas podem ter limites de requisição, mas não exigem pagamento para funcionar.

## O que o MCP entrega

### Mercado
- **Preço atual** — quanto 1 BTC vale agora.
- **Volume** — quanto foi negociado nas últimas 24 horas.
- **Order book** — ordens de compra e venda próximas do preço.
- **Spread** — diferença entre a melhor compra e a melhor venda.
- **Funding rate** — custo periódico entre posições compradas e vendidas em futuros.
- **Open interest** — contratos futuros que continuam abertos.
- **Liquidações** — posições de futuros encerradas à força.

Fonte principal: Binance.

### Volatilidade

Calculada pelo próprio projeto usando o histórico coletado.

Quanto maior o número, maior a oscilação recente do preço.

### Opções

Obtidas gratuitamente da Deribit:

- calls;
- puts;
- open interest;
- volume;
- volatilidade implícita (IV).

### Grandes movimentações

Usamos o mempool público do Bitcoin para encontrar transações grandes que estão aguardando confirmação.

**Importante:** sem uma API paga de etiquetagem de endereços, o projeto não afirma que uma carteira pertence a uma "baleia" ou a uma exchange. Ele mostra apenas grandes transações públicas.

### Entrada e saída de exchanges

O projeto **não inventa esse dado**.

Para calcular com precisão quanto BTC entrou ou saiu das exchanges seria necessário identificar quais endereços pertencem às exchanges. Serviços especializados fazem essa classificação.

Como queremos manter o projeto **100% gratuito**, essa métrica fica explicitamente como indisponível em vez de apresentar um número sem confiabilidade.

### Dados on-chain

Obtidos gratuitamente do mempool.space:

- taxas recomendadas;
- tamanho do mempool;
- hashrate;
- transações recentes.

### Notícias

Notícias sobre Bitcoin são coletadas por RSS público do Google News.

### Sentimento social

Usamos publicações públicas do Reddit e fazemos uma análise textual simples dentro do próprio collector.

Não dependemos de LunarCrush ou outra API paga.

**Importante:** esse sentimento é experimental e não representa um índice profissional de sentimento.

### Correlação

Calculamos a correlação do BTC com:

- ETH;
- S&P 500;
- Nasdaq;
- Dólar (DXY).

São usadas séries públicas do Yahoo Finance.

## Ferramenta principal do MCP

A ferramenta mais simples para usar com um LLM é:

**get_btc_market_data**

Ela retorna todas as informações disponíveis em um único objeto.

Também existem:

- **get_btc_market_snapshot** — principais números atuais.
- **get_btc_history** — histórico dos snapshots.
- **get_btc_features** — indicadores simples.
- **predict_btc_4h** — baseline estatístico de 4 horas.

## Subir com Docker

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

## Não é necessário .env

Você não precisa criar chaves de API para iniciar o projeto.

O objetivo é que um iniciante consiga fazer:

```bash
git clone <repositorio>
cd mcp-btc
docker compose up --build
```

e começar a receber dados.

## Frequência das consultas

Dados rápidos, como preço, order book, funding e open interest:

**a cada 15 segundos.**

Dados mais lentos, como opções, notícias, Reddit, on-chain e correlações:

**a cada 5 minutos.**

Isso reduz a quantidade de requisições e ajuda a respeitar os limites gratuitos das fontes.

## Importante

Este projeto é **educacional**.

Os dados servem para análise e alimentação de um LLM. A previsão de 4 horas é apenas um baseline estatístico e **não é uma previsão financeira validada nem recomendação de compra ou venda**.

## Fontes gratuitas

- Binance — mercado e derivativos.
- Deribit — opções.
- mempool.space — dados públicos da rede Bitcoin.
- Google News RSS — notícias.
- Reddit público — publicações para análise textual de sentimento.
- Yahoo Finance público — séries para correlação.

Nenhuma API key é necessária para executar o collector.
