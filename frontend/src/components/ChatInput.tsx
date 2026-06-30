import { useState, useRef, useEffect, useCallback } from 'react';

interface ChatInputProps {
  onSubmit: (code: string, imageUrl?: string) => void;
  disabled: boolean;
}

const MAX_CODE_LENGTH = 50000;

export default function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [code, setCode] = useState('');
  const [showImageInput, setShowImageInput] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const newHeight = Math.min(ta.scrollHeight, 320);
    ta.style.height = `${Math.max(56, newHeight)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [code, adjustHeight]);

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  const handleSubmit = useCallback(() => {
    const trimmed = code.trim();
    if (trimmed.length === 0 || trimmed.length > MAX_CODE_LENGTH || disabled) return;
    onSubmit(trimmed, imageUrl.trim() || undefined);
    setCode('');
    setImageUrl('');
    setShowImageInput(false);
  }, [code, imageUrl, disabled, onSubmit]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const charCount = code.length;
  const isOverLimit = charCount > MAX_CODE_LENGTH;
  const canSubmit = charCount > 0 && charCount <= MAX_CODE_LENGTH && !disabled;

  return (
    <div className="border-t border-slate-700/60 bg-slate-900/95 backdrop-blur-sm pt-3 pb-4 px-4">
      {/* Image URL input (expandable) */}
      {showImageInput && (
        <div className="mb-2 animate-fade-in">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
            </svg>
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              placeholder="Pega una URL de imagen para contexto adicional..."
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-blue-500 transition-colors"
              aria-label="URL de imagen opcional"
              disabled={disabled}
            />
            {imageUrl && (
              <button
                onClick={() => setImageUrl('')}
                className="text-slate-500 hover:text-slate-300 transition-colors"
                aria-label="Limpiar URL de imagen"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          {imageUrl && (
            <div className="mt-2 max-h-32 overflow-hidden rounded-lg border border-slate-700">
              <img
                src={imageUrl}
                alt="Preview"
                className="w-full h-auto object-contain max-h-32"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Textarea + actions */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Paste your code here for review..."
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 pr-12 text-sm text-slate-100 placeholder:text-slate-500 resize-none outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/20 transition-all scrollbar-thin leading-relaxed font-mono"
            disabled={disabled}
            rows={1}
            spellCheck={false}
            aria-label="Código para revisión"
          />
          {/* Char count */}
          {charCount > 0 && (
            <span
              className={`absolute bottom-2 right-3 text-[10px] font-mono ${
                isOverLimit ? 'text-red-400' : 'text-slate-600'
              }`}
            >
              {charCount}/{MAX_CODE_LENGTH}
            </span>
          )}
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-1.5 flex-shrink-0 pb-0.5">
          {/* Attach image */}
          <button
            onClick={() => setShowImageInput(!showImageInput)}
            className={`p-2.5 rounded-lg transition-colors ${
              showImageInput
                ? 'bg-blue-600/20 text-blue-400'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
            }`}
            aria-label={showImageInput ? 'Ocultar campo de imagen' : 'Adjuntar imagen'}
            disabled={disabled}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
              />
            </svg>
          </button>

          {/* Send */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="p-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-600 text-white transition-all duration-200 disabled:cursor-not-allowed"
            aria-label="Enviar código para revisión"
          >
            {disabled ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Hint */}
      {!disabled && charCount === 0 && (
        <p className="text-[10px] text-slate-600 mt-1.5 text-center">
          <kbd className="px-1 py-0.5 bg-slate-800 rounded text-[10px] font-mono border border-slate-700">
            Ctrl+Enter
          </kbd>{' '}
          para enviar
        </p>
      )}
      {isOverLimit && (
        <p className="text-[10px] text-red-400 mt-1.5 text-center">
          El código excede el límite de {MAX_CODE_LENGTH.toLocaleString()} caracteres
        </p>
      )}
    </div>
  );
}
