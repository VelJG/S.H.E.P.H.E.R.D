const env = (import.meta as any).env ?? {};

export const AGENT_URL = (env.VITE_AGENT_URL || 'http://localhost:8100').replace(/\/+$/, '');

export type AgentPrediction = {
  zoneId: string;
  zoneName: string;
  risk: 'low' | 'medium' | 'high';
  etaSeconds: number | null;
  reason: string;
  recommendation: string;
};

export type AgentChatResponse = {
  answer: string;
  intent: string;
  usedTools: string[];
  predictions: AgentPrediction[];
  metadata: Record<string, any>;
};

export type AgentHealth = {
  ok: boolean;
  service: string;
  dataMode: string;
  zones: number;
};

export type AgentMetricPayload = {
  zoneId: string;
  timestamp: string;
  personCount: number;
  queueLength: number;
  waitSec: number;
  status: string;
  source?: string;
  congestionScore?: number;
};

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) throw new Error(`Agent ${response.status}: ${text.slice(0, 180)}`);
  return JSON.parse(text) as T;
}

export async function getAgentHealth(): Promise<AgentHealth> {
  const response = await fetch(`${AGENT_URL}/agent/health`, { cache: 'no-store' });
  return parseJsonResponse<AgentHealth>(response);
}

export async function askAgent(message: string, mode: 'auto' | 'predict' | 'copilot' | 'report' = 'auto'): Promise<AgentChatResponse> {
  const response = await fetch(`${AGENT_URL}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, mode }),
  });
  return parseJsonResponse<AgentChatResponse>(response);
}

export async function ingestAgentMetrics(metrics: AgentMetricPayload[], ingestUrl = `${AGENT_URL}/agent/ingest/metrics`): Promise<void> {
  if (!metrics.length) return;
  const response = await fetch(ingestUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ metrics }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Agent ingest ${response.status}: ${text.slice(0, 180)}`);
  }
}
