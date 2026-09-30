CREATE TABLE IF NOT EXISTS market_snapshots (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume_24h DOUBLE PRECISION,
    spread DOUBLE PRECISION,
    funding_rate DOUBLE PRECISION,
    open_interest DOUBLE PRECISION,
    data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_ts
ON market_snapshots(ts DESC);
