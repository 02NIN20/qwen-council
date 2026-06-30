import { useRef, useEffect } from 'react';
import type { ChatMessageData } from '../types';
import { AGENTS } from '../types';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatViewProps {
  messages: ChatMessageData[];
  onSubmit: (code: string, files?: { filename: string; content: string }[], imageUrl?: string) => void;
  disabled: boolean;
}

export default function ChatView({ messages, onSubmit, disabled }: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 150;
    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-screen bg-retro-bg">
      {/* Scrollable message area */}
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
                Multi-agent code review system. Drop a file below and let
                six specialized agents analyze it.
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

              <div className="mt-8 text-[10px] text-gray-700">
                <kbd className="px-1.5 py-0.5 bg-retro-bg border border-retro-border font-mono text-gray-600">
                  Ctrl+Enter
                </kbd>{' '}
                to send
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
        </div>
        <div ref={bottomRef} />
      </div>

      {/* Fixed input area */}
      <ChatInput onSubmit={onSubmit} disabled={disabled} />
    </div>
  );
}
