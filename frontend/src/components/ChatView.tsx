import { useRef, useEffect, useState, useCallback } from 'react';
import type { ChatMessageData } from '../types';
import { AGENTS } from '../types';

const REVIEW_AGENTS = AGENTS.slice(0, 6);
const CHAT_AGENTS = AGENTS.slice(6);
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatViewProps {
  messages: ChatMessageData[];
  onSubmit: (code: string, files?: { filename: string; content: string }[], images?: { filename: string; content: string; mime_type: string }[], instruction?: string) => void;
  onChatSubmit: (message: string) => void;
  disabled: boolean;
  sessionId?: string;
}

export default function ChatView({ messages, onSubmit, onChatSubmit, disabled, sessionId }: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [followUpResponse, setFollowUpResponse] = useState('');
  const [followUpLoading, setFollowUpLoading] = useState(false);

  // Reset follow-up response when switching sessions
  useEffect(() => {
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

  // Follow-up API call — receives the question text directly from ChatInput
  const handleFollowUp = useCallback(async (question: string) => {
    if (!question.trim() || !sessionId) return;
    setFollowUpLoading(true);

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
  }, [sessionId, messages]);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
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

              <p className="text-xs text-gray-500 max-w-md leading-relaxed mb-4 uppercase tracking-wider">
                Multi-agent system with two modes.
              </p>
              <div className="flex flex-col items-center gap-4 w-full max-w-lg mx-auto">
                {/* Chat Agents */}
                <div className="w-full">
                  <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-widest mb-2 text-center">
                    &gt; CHAT &mdash; 8 personality agents
                  </p>
                  <div className="flex flex-wrap justify-center gap-1.5 text-xs">
                    {CHAT_AGENTS.map((agent) => (
                      <span
                        key={agent.id}
                        className="agent-pill"
                        style={{ borderLeft: `3px solid ${agent.color}` }}
                      >
                        <span style={{ color: agent.color }}>{agent.icon}</span>
                        <span className="text-gray-400">{agent.name}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Code Review Agents */}
                <div className="w-full">
                  <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-widest mb-2 text-center">
                    &gt; CODE REVIEW &mdash; 6 specialized agents
                  </p>
                  <div className="flex flex-wrap justify-center gap-1.5 text-xs">
                    {REVIEW_AGENTS.map((agent) => (
                      <span
                        key={agent.id}
                        className="agent-pill"
                        style={{ borderLeft: `3px solid ${agent.color}` }}
                      >
                        <span style={{ color: agent.color }}>[{agent.icon}]</span>
                        <span className="text-gray-400">{agent.name}</span>
                      </span>
                    ))}
                  </div>
                </div>
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

      {/* Single input bar — adapts to follow-up mode when last message is a report */}
      <ChatInput
        onSubmit={onSubmit}
        onChatSubmit={onChatSubmit}
        disabled={disabled || followUpLoading}
        followUpMode={lastMessageIsReport && !!sessionId}
        onFollowUpSubmit={handleFollowUp}
      />
    </div>
  );
}
