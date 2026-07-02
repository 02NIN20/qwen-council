import type { ReviewResponse, SessionDetail, SessionSummary, ChatResponse } from '../types';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => '');
    throw new Error(
      `API error ${response.status}: ${response.statusText}${errorBody ? ` — ${errorBody}` : ''}`
    );
  }

  return response.json() as Promise<T>;
}

export async function submitReview(
  code: string,
  files?: { filename: string; content: string; language?: string }[],
  instruction?: string,
  mode?: 'light' | 'full',
  session_id?: string,
): Promise<ReviewResponse> {
  return fetchJson<ReviewResponse>(`${API_BASE}/review`, {
    method: 'POST',
    body: JSON.stringify({
      code: code || undefined,
      files: files || undefined,
      instruction: instruction || undefined,
      mode: mode || undefined,
      session_id,
    }),
  });
}

export async function getSessions(limit = 20): Promise<SessionSummary[]> {
  return fetchJson<SessionSummary[]>(`${API_BASE}/sessions?limit=${limit}`);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return fetchJson<SessionDetail>(`${API_BASE}/sessions/${sessionId}`);
}

export async function sendChatMessage(
  message: string,
  sessionId?: string,
  context?: string,
  files?: { filename: string; content: string; language?: string }[],
  images?: { filename: string; content: string; mime_type: string }[],
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(`${API_BASE}/chat`, {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId,
      context,
      files: files || undefined,
      images: images || undefined,
    }),
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export async function healthCheck(): Promise<{ status: string; version?: string; db_connected?: boolean }> {
  return fetchJson(`${API_BASE}/health`);
}
