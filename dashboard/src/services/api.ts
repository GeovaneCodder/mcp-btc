import type { Prediction, Snapshot } from "../types";

const base = "";

export async function getSnapshot(): Promise<Snapshot> {
  const response = await fetch(base + "/api/snapshot");
  if (!response.ok) throw new Error("Falha ao carregar snapshot");
  return response.json();
}

export async function getHistory(limit = 200): Promise<Snapshot[]> {
  const response = await fetch(base + "/api/history?limit=" + limit);
  if (!response.ok) throw new Error("Falha ao carregar histórico");
  return response.json();
}

export async function getPrediction(): Promise<Prediction> {
  const response = await fetch(base + "/api/predict/4h");
  if (!response.ok) throw new Error("Falha ao carregar previsão");
  return response.json();
}
