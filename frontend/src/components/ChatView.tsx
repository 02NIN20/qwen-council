import { useRef, useEffect, useState, useCallback } from 'react';
import type { ChatMessageData } from '../types';
import { AGENTS } from '../types';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatViewProps {
  messages: ChatMessageData[];
  onSubmit: (code: string, files?: { filename: string; content: string }[], imageUrl?: string, instruction?: string) => void;
  onChatSubmit: (message: string) => void;
  disabled: boolean;
  sessionId?: string;
}

export default function ChatView({ messages, onSubmit, onChatSubmit, disabled, sessionId }: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [followUp, setFollowUp] = useState('');
  const [followUpResponse, setFollowUpResponse] = useState('');
  const [followUpLoading, setFollowUpLoading] = useState(false);

  // Reset follow-up state when switching sessions
  useEffect(() => {
    setFollowUp('');
    setFollowUpResponse('');
  }, [sessionId]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 150;
    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, followUpResponse]);

  const hasMessages = messages.length > 0;
  const lastMessageIsReport = hasMessages && messages[messages.length - 1].role === 'report';

  // Follow-up API call
  const handleFollowUp = useCallback(async () => {
    if (!followUp.trim() || !sessionId) return;
    setFollowUpLoading(true);
    const question = followUp.trim();
    setFollowUp('');

    // Build context from the report
    const reportMsg = messages.find(m => m.role === 'report');
    const context = reportMsg?.report
      ? JSON.stringify(reportMsg.report.findings.slice(0, 5))
      : '';

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: question,
          context,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setFollowUpResponse(data.response || 'I could not generate a response.');
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setFollowUpResponse('Request timed out after 30 seconds. Please try again.');
      } else {
        setFollowUpResponse(err instanceof Error ? err.message : 'Error getting response');
      }
    }
    setFollowUpLoading(false);
  }, [followUp, sessionId, messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto scrollbar-retro px-4 py-6"
      >
        <div className="max-w-3xl mx-auto space-y-4">
          {!hasMessages ? (
            /* ── Retro Welcome Screen ── */
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center message-enter">
              {/* ">_" prompt symbol */}
              <div className="mb-4">
                <span className="text-5xl font-bold text-retro-cyan">&gt;_</span>
              </div>

              {/* Title with blinking cursor */}
              <h1 className="text-2xl font-bold text-retro-cyan mb-2 tracking-tight">
                Qwen Council
                <span className="inline-block w-3 h-6 bg-retro-cyan ml-1.5 animate-blink align-middle" />
              </h1>

              <p className="text-xs text-gray-500 max-w-md leading-relaxed mb-6 uppercase tracking-wider">
                Multi-agent code review system. Drop files below and let
                six specialized agents analyze them.
              </p>

              {/* Agent badges — sharp retro style */}
              <div className="flex flex-wrap justify-center gap-2 text-xs">
                {AGENTS.map((agent) => (
                  <span
                    key={agent.id}
                    className="agent-pill"
                    style={{
                      borderLeft: `3px solid ${agent.color}`,
                    }}
                  >
                    <span style={{ color: agent.color }}>[{agent.icon}]</span>
                    <span className="text-gray-400">{agent.name}</span>
                  </span>
                ))}
              </div>
            </div>
          ) : (
            /* ── Messages ── */
            messages.map((msg) => (
              <div key={msg.id}>
                <ChatMessage message={msg} />
              </div>
            ))
          )}

          {/* Follow-up Q&A (shown after report) */}
          {followUpResponse && (
            <div className="chat-message message-enter" style={{ borderLeft: '3px solid #00fff8' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold text-retro-cyan">&gt; FOLLOW-UP</span>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{followUpResponse}</p>
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* Follow-up input (shown after report) */}
      {lastMessageIsReport && !disabled && (
        <div className="border-t border-retro-border bg-retro-surface px-4 py-2">
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            <input
              type="text"
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleFollowUp(); } }}
              placeholder="Ask a follow-up question about this review..."
              className="flex-1 bg-retro-bg border border-retro-border px-3 py-2 text-sm text-gray-300 placeholder:text-gray-600 outline-none focus:border-retro-cyan transition-colors font-mono"
              disabled={followUpLoading}
              aria-label="Follow-up question"
            />
            <button
              onClick={handleFollowUp}
              disabled={!followUp.trim() || followUpLoading}
              className="p-2 border border-retro-cyan text-retro-cyan hover:bg-retro-cyan hover:text-black transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Send follow-up"
            >
              {followUpLoading ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Main chat input */}
      {!lastMessageIsReport && (
        <ChatInput onSubmit={onSubmit} onChatSubmit={onChatSubmit} disabled={disabled} />
      )}
    </div>
  );
}
