import type { Report } from '../types';

/* ─── Types ─────────────────────────────────────────────────────────── */

export interface StreamReviewRequest {
  code?: string;
  files?: { filename: string; content: string; language?: string }[];
  images?: { filename: string; content: string; mime_type: string }[];
  instruction?: string;
}

export interface StreamReviewResponse {
  sessionId: string;
  report: Report;
}

export interface StreamCallbacks {
  onRoundStart?: (round: number, totalRounds: number) => void;
  onAgentStart?: (agent: string, round: number) => void;
  onAgentComplete?: (agent: string, round: number, findingsCount: number) => void;
  onRoundComplete?: (round: number, totalFindings: number) => void;
  onSynthesisComplete?: (consolidatedCount: number) => void;
  onNegotiationStart?: (disputedCount: number) => void;
  onNegotiationComplete?: (resolved: number) => void;
  onComplete?: (sessionId: string, report: Report) => void;
  onError?: (error: string) => void;
}

/* ─── SSE line parser ──────────────────────────────────────────────── */

type SSEData = Record<string, unknown>;

/**
 * Parse a single SSE `data:` JSON line and dispatch to the matching callback.
 */
function dispatchEvent(
  eventType: string,
  rawData: string,
  callbacks: StreamCallbacks,
): void {
  let data: SSEData;
  try {
    data = JSON.parse(rawData) as SSEData;
  } catch {
    // If JSON parsing fails, treat rawData as an error message
    callbacks.onError?.(`Failed to parse SSE data: ${rawData}`);
    return;
  }

  switch (eventType) {
    case 'round_start': {
      const round = Number(data.round ?? 0);
      const totalRounds = Number(data.total_rounds ?? 3);
      callbacks.onRoundStart?.(round, totalRounds);
      break;
    }
    case 'agent_start': {
      const agent = String(data.agent ?? '');
      const round = Number(data.round ?? 0);
      callbacks.onAgentStart?.(agent, round);
      break;
    }
    case 'agent_complete': {
      const agent = String(data.agent ?? '');
      const round = Number(data.round ?? 0);
      const findingsCount = Number(data.findings_count ?? 0);
      callbacks.onAgentComplete?.(agent, round, findingsCount);
      break;
    }
    case 'round_complete': {
      const round = Number(data.round ?? 0);
      const totalFindings = Number(data.total_findings ?? 0);
      callbacks.onRoundComplete?.(round, totalFindings);
      break;
    }
    case 'synthesis_complete': {
      const consolidatedCount = Number(data.consolidated_count ?? 0);
      callbacks.onSynthesisComplete?.(consolidatedCount);
      break;
    }
    case 'negotiation_start': {
      const disputedCount = Number(data.disputed_count ?? 0);
      callbacks.onNegotiationStart?.(disputedCount);
      break;
    }
    case 'negotiation_complete': {
      const resolved = Number(data.resolved ?? 0);
      callbacks.onNegotiationComplete?.(resolved);
      break;
    }
    case 'complete': {
      const sessionId = String(data.session_id ?? '');
      const report = data.report as Report;
      callbacks.onComplete?.(sessionId, report);
      break;
    }
    case 'error': {
      const errorMsg = String(data.error ?? data.message ?? 'Unknown SSE error');
      callbacks.onError?.(errorMsg);
      break;
    }
    default:
      // Unknown event type — ignore
      break;
  }
}

/* ─── Main streaming function ──────────────────────────────────────── */

const API_BASE = '/api';

/**
 * Subscribes to the SSE streaming endpoint (`POST /api/review/stream`)
 * using `fetch` with a `ReadableStream` (because EventSource does not
 * support POST requests).
 *
 * Calls the appropriate callback for each event received from the server.
 * Resolves with `{ sessionId, report }` when the stream completes.
 */
export function streamReview(
  payload: StreamReviewRequest,
  callbacks: StreamCallbacks,
): Promise<StreamReviewResponse> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();

    // Prepare the request
    fetch(`${API_BASE}/review/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const errorBody = await response.text().catch(() => '');
          throw new Error(
            `Stream API error ${response.status}: ${response.statusText}${errorBody ? ` — ${errorBody}` : ''}`,
          );
        }

        const bodyReader = response.body?.getReader();
        if (!bodyReader) {
          throw new Error('Response body is not readable (no ReadableStream)');
        }
        const reader: ReadableStreamDefaultReader<Uint8Array> = bodyReader;

        const decoder = new TextDecoder();
        let buffer = '';
        let currentEventType = 'message';

        // Read the stream chunk by chunk
        function pump(): void {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                // Process any remaining data in the buffer
                if (buffer.trim()) {
                  processLines(buffer);
                }
                return;
              }

              buffer += decoder.decode(value, { stream: true });

              // Process complete lines (SSE events separated by \n\n)
              const parts = buffer.split('\n\n');
              // The last part may be incomplete — keep it in the buffer
              buffer = parts.pop() ?? '';

              for (const part of parts) {
                processLines(part);
              }

              pump();
            })
            .catch((err: unknown) => {
              // Only reject if not aborted
              if (err instanceof Error && err.name === 'AbortError') return;
              const msg = err instanceof Error ? err.message : 'Stream read error';
              callbacks.onError?.(msg);
              reject(new Error(msg));
            });
        }

        /**
         * Process lines within a single SSE message block (between \n\n separators).
         * Lines look like:
         *   event: round_start
         *   data: {"round":1,"total_rounds":3}
         */
        function processLines(block: string): void {
          const lines = block.split('\n').map((l) => l.trim()).filter(Boolean);

          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              const rawData = line.slice(5).trim();
              dispatchEvent(currentEventType, rawData, callbacks);
            }
            // Ignore other fields (id:, retry:, etc.)
          }
        }

        pump();
      })
      .catch((err: unknown) => {
        // Initial fetch failure
        const msg = err instanceof Error ? err.message : 'Stream fetch failed';
        callbacks.onError?.(msg);
        reject(new Error(msg));
      });
  });
}
