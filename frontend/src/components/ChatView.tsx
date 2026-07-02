import { useRef, useEffect, useState, useCallback } from 'react';
import type { ChatMessageData } from '../types';
import { AGENTS } from '../types';
import { sendChatMessage } from '../api/council';

const CORE_AGENTS = AGENTS;
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatViewProps {
  messages: ChatMessageData[];
  onSubmit: (code: string, files?: { filename: string; content: string }[], images?: { filename: string; content: string; mime_type: string }[], instruction?: string, mode?: 'light' | 'full') => void;
  onChatSubmit: (message: string, files?: { filename: string; content: string; language?: string }[], images?: { filename: string; content: string; mime_type: string }[]) => void;
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

    try {
      const response = await sendChatMessage(question, sessionId, undefined, undefined, undefined);
      setFollowUpResponse(response.response || 'I could not generate a response.');
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setFollowUpResponse('Request timed out after 30 seconds. Please try again.');
      } else {
        setFollowUpResponse(err instanceof Error ? err.message : 'Error getting response');
      }
    }
    setFollowUpLoading(false);
  }, [sessionId]);

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
                Multi-Agent Council
                <span className="inline-block w-3 h-6 bg-retro-cyan ml-1.5 animate-blink align-middle" />
              </h1>

              <p className="text-xs text-gray-500 max-w-md leading-relaxed mb-6 uppercase tracking-wider">
                6 agents debate, cross-reference, and converge on every question.
              </p>

              {/* Agent Society pills */}
              <div className="w-full max-w-lg mb-6">
                <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-widest mb-2 text-center">
                  &gt; AGENT SOCIETY
                </p>
                <div className="flex flex-wrap justify-center gap-1.5 text-xs">
                  {CORE_AGENTS.map((agent) => (
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

              {/* Example prompts */}
              <div className="w-full max-w-lg">
                <p className="text-[10px] text-gray-600 font-bold uppercase tracking-widest mb-2 text-center">
                  Try asking the council...
                </p>
                <div className="grid grid-cols-1 gap-1.5 text-left">
                  {[
                    { icon: '[>]', text: 'Write a Python script that scrapes Hacker News and emails the top 5 stories', color: 'text-retro-yellow' },
                    { icon: '[?]', text: 'Explain the SOLID principles with code examples in TypeScript', color: 'text-retro-cyan' },
                    { icon: '[!]', text: 'Review this architecture: a React SPA with FastAPI backend and PostgreSQL, deployed on ECS', color: 'text-retro-magenta' },
                    { icon: '[*]', text: 'Compare Rust vs Go for building a high-throughput message queue', color: 'text-retro-green' },
                  ].map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => onChatSubmit(ex.text)}
                      disabled={disabled}
                      className="w-full text-left px-3 py-2 border border-retro-border bg-retro-bg hover:border-retro-cyan hover:bg-retro-surface transition-colors group"
                    >
                      <span className={`text-[10px] font-mono font-bold mr-2 ${ex.color}`}>{ex.icon}</span>
                      <span className="text-xs text-gray-400 group-hover:text-gray-200 transition-colors">{ex.text}</span>
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-gray-700 text-center mt-3">
                  Or attach code files + images for a full multi-agent review with SSE streaming.
                </p>
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
