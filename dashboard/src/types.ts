export interface Snapshot {
  ts: string;
  symbol: string;
  price: number;
  volume_24h: number;
  bid: number;
  ask: number;
  spread: number;
  bid_volume: number;
  ask_volume: number;
  funding_rate: number;
  open_interest: number;
  liquidation_long: number;
  liquidation_short: number;
}

export interface Prediction {
  timestamp: string;
  horizon: string;
  current_price: number;
  predicted_price: number;
  predicted_return: number;
  direction: "UP" | "DOWN" | "SIDEWAYS";
  volatility_per_sample: number;
  samples: number;
  model: string;
  warning: string;
}
