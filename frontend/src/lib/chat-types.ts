export type ChatRole = "user" | "assistant";

export interface Source {
  id: number;
  title: string;
  source: string; // filename
  page: number;
  score: number;
}

export interface Metrics {
  region: string;
  timestamp: string;
  ndvi: number | null;
  fvc: number | null;
  risk_level: number;
  wind_speed: number | null;
  soil_moisture: number | null;
  last_alert:
    | { level: number; message: string; timestamp: string }
    | null;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Source[];
  metrics?: Metrics | null;
  streaming?: boolean;
  error?: string;
}

export interface ChatRequest {
  question: string;
  region_hint?: string | null;
}
