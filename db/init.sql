CREATE TABLE IF NOT EXISTS market_snapshots (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume_24h DOUBLE PRECISION,
    bid DOUBLE PRECISION,
    ask DOUBLE PRECISION,
    spread DOUBLE PRECISION,
    bid_volume DOUBLE PRECISION,
    ask_volume DOUBLE PRECISION,
    funding_rate DOUBLE PRECISION,
    open_interest DOUBLE PRECISION,
    liquidation_long DOUBLE PRECISION DEFAULT 0,
    liquidation_short DOUBLE PRECISION DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_ts
ON market_snapshots(ts DESC);
