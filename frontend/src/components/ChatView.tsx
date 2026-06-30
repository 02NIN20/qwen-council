import { useRef, useEffect } from 'react';
import type { ChatMessageData } from '../types';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatViewProps {
  messages: ChatMessageData[];
  onSubmit: (code: string, imageUrl?: string) => void;
  disabled: boolean;
}

export default function ChatView({ messages, onSubmit, disabled }: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    // Check if user is near bottom (within 150px threshold)
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 150;
    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-screen bg-slate-900">
      {/* Scrollable message area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6"
      >
        <div className="max-w-3xl mx-auto space-y-6">
          {!hasMessages ? (
            /* ── Welcome screen ── */
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-emerald-500/20 border border-slate-700/50 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                </svg>
              </div>
              <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">
                Qwen Council
              </h1>
              <p className="text-sm text-slate-400 max-w-md leading-relaxed mb-6">
                Multi-agent code review system. Paste your code below and let
                six specialized agents analyze it for security, architecture,
                quality, performance, UX, and visual design issues.
              </p>
              <div className="flex flex-wrap justify-center gap-3 text-xs">
                <span className="px-3 py-1.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                  [S] Seguridad
                </span>
                <span className="px-3 py-1.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  [A] Arquitectura
                </span>
                <span className="px-3 py-1.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
                  [Q] Calidad
                </span>
                <span className="px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  [P] Performance
                </span>
                <span className="px-3 py-1.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  [U] UX
                </span>
                <span className="px-3 py-1.5 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20">
                  [V] Visión
                </span>
              </div>
              <div className="mt-8 text-xs text-slate-600">
                <kbd className="px-1.5 py-0.5 bg-slate-800 rounded border border-slate-700 font-mono">
                  Ctrl+Enter
                </kbd>{' '}
                para enviar
              </div>
            </div>
          ) : (
            /* ── Messages ── */
            messages.map((msg, idx) => (
              <div
                key={msg.id}
                className={`${msg.role === 'user' ? 'pl-0' : 'pl-0'}`}
              >
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
