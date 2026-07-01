import { useState, useRef, useEffect, useCallback, type DragEvent, type ChangeEvent } from 'react';

interface ChatInputProps {
  onSubmit: (code: string, files: { filename: string; content: string }[], images?: { filename: string; content: string; mime_type: string }[], instruction?: string) => void;
  onChatSubmit: (message: string) => void;
  disabled: boolean;
  /** Show simplified follow-up mode (no file attach, chat-only) */
  followUpMode?: boolean;
  /** Called instead of onChatSubmit when followUpMode is true */
  onFollowUpSubmit?: (message: string) => void;
}

const ACCEPTED_EXTENSIONS = [
  '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json',
  '.md', '.txt', '.sql', '.java', '.cpp', '.c', '.go', '.rs',
  '.rb', '.php', '.swift', '.kt', '.yaml', '.yml', '.toml',
  '.sh', '.bash', '.zsh', '.dockerfile', '.graphql', '.proto',
];

const ACCEPT_STRING = ACCEPTED_EXTENSIONS.join(',');
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'];
const IMAGE_ACCEPT_STRING = IMAGE_EXTENSIONS.join(',');
const MAX_FILE_SIZE = 50 * 1024; // 50 KB
const MAX_IMAGE_SIZE = 500 * 1024; // 500 KB

interface SelectedFile {
  name: string;
  size: number;
  content: string;
}

interface SelectedImage {
  name: string;
  size: number;
  content: string; // base64
  mime_type: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const FILE_ICONS: Record<string, string> = {
  py: 'PY', js: 'JS', ts: 'TS', jsx: 'JSX', tsx: 'TSX',
  html: 'HTML', css: 'CSS', json: 'JSON', md: 'MD', sql: 'SQL',
  java: 'JAVA', cpp: 'CPP', c: 'C', go: 'GO', rs: 'RS',
  rb: 'RB', php: 'PHP', swift: 'SWIFT', kt: 'KT', yaml: 'YAML',
  yml: 'YML', toml: 'TOML', sh: 'SH', dockerfile: 'DOCKER',
};

function fileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return FILE_ICONS[ext] || 'FILE';
}

export default function ChatInput({ onSubmit, onChatSubmit, disabled, followUpMode, onFollowUpSubmit }: ChatInputProps) {
  const [files, setFiles] = useState<SelectedFile[]>([]);
  const [images, setImages] = useState<SelectedImage[]>([]);
  const [chatText, setChatText] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Reset file/image state when toggling follow-up mode
  useEffect(() => {
    if (followUpMode) {
      setFiles([]);
      setImages([]);
    }
  }, [followUpMode]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
    }
  }, [chatText]);

  // Reset file input value after selection
  useEffect(() => {
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [files]);

  useEffect(() => {
    if (imageInputRef.current) imageInputRef.current.value = '';
  }, [images]);

  // ── File handling ─────────────────────────────────────────────

  const readFiles = useCallback((fileList: FileList) => {
    const pending: SelectedFile[] = [];
    let hasOversized = false;
    for (const f of Array.from(fileList)) {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (IMAGE_EXTENSIONS.includes(ext)) continue; // skip images, handle separately
      if (f.size > MAX_FILE_SIZE) { hasOversized = true; continue; }
      pending.push({ name: f.name, size: f.size, content: '' });
    }
    if (hasOversized) {
      alert(`Some files were skipped (max ${formatFileSize(MAX_FILE_SIZE)} each).`);
    }
    if (pending.length === 0) return;

    let loaded = 0;
    const results: SelectedFile[] = [];
    for (const pf of pending) {
      const found = Array.from(fileList).find((f) => f.name === pf.name);
      if (!found) continue;
      const reader = new FileReader();
      reader.onload = () => {
        results.push({ name: pf.name, size: pf.size, content: reader.result as string });
        loaded++;
        if (loaded === pending.length) setFiles((prev) => [...prev, ...results]);
      };
      reader.onerror = () => { loaded++; };
      reader.readAsText(found);
    }
  }, []);

  const readImages = useCallback((fileList: FileList) => {
    const pending: SelectedImage[] = [];
    let hasOversized = false;
    for (const f of Array.from(fileList)) {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (!IMAGE_EXTENSIONS.includes(ext)) continue;
      if (f.size > MAX_IMAGE_SIZE) { hasOversized = true; continue; }
      pending.push({
        name: f.name,
        size: f.size,
        content: '',
        mime_type: f.type || 'image/png',
      });
    }
    if (hasOversized) {
      alert(`Some images were skipped (max ${formatFileSize(MAX_IMAGE_SIZE)} each).`);
    }
    if (pending.length === 0) return;

    let loaded = 0;
    const results: SelectedImage[] = [];
    for (const pf of pending) {
      const found = Array.from(fileList).find((f) => f.name === pf.name);
      if (!found) continue;
      const reader = new FileReader();
      reader.onload = () => {
        // Extract base64 from data URL
        const dataUrl = reader.result as string;
        const base64 = dataUrl.split(',')[1] || dataUrl;
        results.push({ name: pf.name, size: pf.size, content: base64, mime_type: pf.mime_type });
        loaded++;
        if (loaded === pending.length) setImages((prev) => [...prev, ...results]);
      };
      reader.onerror = () => { loaded++; };
      reader.readAsDataURL(found);
    }
  }, []);

  const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const fl = e.target.files;
    if (!fl || fl.length === 0) return;
    readFiles(fl);
    readImages(fl);
  }, [readFiles, readImages]);

  const handleImageSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const fl = e.target.files;
    if (!fl || fl.length === 0) return;
    readImages(fl);
  }, [readImages]);

  const handleRemoveFile = useCallback((idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleRemoveImage = useCallback((idx: number) => {
    setImages((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // ── Drag & drop ──────────────────────────────────────────────

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const fl = e.dataTransfer.files;
    if (!fl || fl.length === 0) return;
    readFiles(fl);
    readImages(fl);
  }, [readFiles, readImages]);

  // ── Submit logic ──────────────────────────────────────────────

  const handleSend = useCallback(() => {
    if (disabled) return;

    // Follow-up mode: call onFollowUpSubmit
    if (followUpMode && chatText.trim()) {
      onFollowUpSubmit?.(chatText.trim());
      setChatText('');
      return;
    }

    // If files or images are attached → code review mode
    if (files.length > 0 || images.length > 0) {
      const filePayload = files.map((f) => ({
        filename: f.name,
        content: f.content,
      }));
      const imagePayload = images.length > 0 ? images.map((img) => ({
        filename: img.name,
        content: img.content,
        mime_type: img.mime_type,
      })) : undefined;
      const instruction = chatText.trim() || undefined;
      onSubmit('', filePayload, imagePayload, instruction);
      setFiles([]);
      setImages([]);
      setChatText('');
      return;
    }

    // If text only → general chat mode
    if (chatText.trim()) {
      onChatSubmit(chatText.trim());
      setChatText('');
    }
  }, [files, images, chatText, disabled, onSubmit, onChatSubmit, followUpMode, onFollowUpSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter for newline (default behavior), Enter alone sends
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const canSend = (files.length > 0 || images.length > 0 || chatText.trim().length > 0) && !disabled;

  // ── Render ──────────────────────────────────────────────────

  return (
    <div
      className="relative border-t-2 border-retro-border bg-retro-surface"
      onDragOver={!followUpMode ? handleDragOver : undefined}
      onDragLeave={!followUpMode ? handleDragLeave : undefined}
      onDrop={!followUpMode ? handleDrop : undefined}
    >
      {/* ── Drag overlay (main mode only) ── */}
      {!followUpMode && isDragOver && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#0d1117]/90 border-2 border-dashed border-retro-cyan">
          <div className="text-center">
            <svg className="w-10 h-10 mx-auto text-retro-cyan mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="text-retro-cyan font-bold text-sm tracking-wider uppercase">Drop files here</p>
            <p className="text-gray-500 text-xs mt-1">.py .js .ts .html .css .json .png .jpg ...</p>
          </div>
        </div>
      )}

      {/* ── Hidden file inputs (main mode only) ── */}
      {!followUpMode && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_STRING}
            multiple
            className="hidden"
            onChange={handleFileSelect}
            aria-hidden="true"
          />
          <input
            ref={imageInputRef}
            type="file"
            accept={IMAGE_ACCEPT_STRING}
            multiple
            className="hidden"
            onChange={handleImageSelect}
            aria-hidden="true"
          />
        </>
      )}

      {/* ── Main input bar ── */}
      <div className="flex items-end gap-1.5 px-3 py-2.5">
        {/* Attach files button (main mode only) */}
        {!followUpMode && (
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="p-2 text-gray-500 hover:text-retro-cyan transition-colors disabled:opacity-30 flex-shrink-0"
            aria-label="Attach files"
            title="Attach files"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
            </svg>
          </button>
        )}

        {/* Attach image button (main mode only) */}
        {!followUpMode && (
          <button
            onClick={() => imageInputRef.current?.click()}
            disabled={disabled}
            className="p-2 text-gray-500 hover:text-retro-cyan transition-colors disabled:opacity-30 flex-shrink-0"
            aria-label="Attach images"
            title="Attach images"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
            </svg>
          </button>
        )}

        {/* ── File chips + textarea ── */}
        <div className="flex-1 min-w-0">
          {/* File chips (main mode only) */}
          {!followUpMode && files.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-1.5">
              {files.map((f, idx) => (
                <span
                  key={`file-${f.name}-${idx}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#161b22] border border-retro-border rounded text-xs text-gray-300 font-mono"
                >
                  <span className="text-[10px] font-bold text-retro-cyan">{fileIcon(f.name)}</span>
                  <span className="max-w-[120px] truncate">{f.name}</span>
                  <span className="text-[10px] text-gray-500">({formatFileSize(f.size)})</span>
                  <button
                    onClick={() => handleRemoveFile(idx)}
                    className="ml-0.5 text-gray-500 hover:text-retro-red transition-colors"
                    aria-label={`Remove ${f.name}`}
                  >x</button>
                </span>
              ))}
            </div>
          )}

          {/* Image chips (main mode only) */}
          {!followUpMode && images.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-1.5">
              {images.map((img, idx) => (
                <span
                  key={`img-${img.name}-${idx}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#161b22] border border-retro-border rounded text-xs text-gray-300 font-mono"
                >
                  <span className="text-[10px] font-bold text-retro-green">IMG</span>
                  <span className="max-w-[120px] truncate">{img.name}</span>
                  <span className="text-[10px] text-gray-500">({formatFileSize(img.size)})</span>
                  <button
                    onClick={() => handleRemoveImage(idx)}
                    className="ml-0.5 text-gray-500 hover:text-retro-red transition-colors"
                    aria-label={`Remove ${img.name}`}
                  >x</button>
                </span>
              ))}
            </div>
          )}

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              followUpMode
                ? "Ask a follow-up question about this review..."
                : files.length > 0 || images.length > 0
                  ? "Add instructions for the review... (or press Enter to send)"
                  : "Ask the expert panel a question, paste code, or attach files..."
            }
            className="w-full bg-transparent text-sm text-gray-200 placeholder:text-gray-600 outline-none resize-none font-mono leading-relaxed"
            rows={1}
            disabled={disabled}
            aria-label="Message input"
          />
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={`p-2 rounded-lg transition-all duration-150 flex-shrink-0 ${
            canSend
              ? 'bg-retro-cyan text-black hover:bg-retro-cyan/90'
              : 'bg-gray-800 text-gray-600'
          } disabled:opacity-40 disabled:cursor-not-allowed`}
          aria-label="Send"
        >
          {disabled ? (
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          )}
        </button>
      </div>

      {/* ── Footer hint ── */}
      {!disabled && !followUpMode && files.length === 0 && images.length === 0 && !chatText.trim() && (
        <div className="pb-2 px-4">
          <p className="text-[10px] text-gray-700 text-center flex items-center justify-center gap-3">
            <span>Enter to send . Shift+Enter for new line</span>
            <span className="text-gray-800">.</span>
            <span>Drag and drop files to attach</span>
          </p>
        </div>
      )}
      {!disabled && !followUpMode && (files.length > 0 || images.length > 0) && (
        <div className="pb-2 px-4">
          <p className="text-[10px] text-gray-700 text-center">
            Files attached . Press Enter to start code review
          </p>
        </div>
      )}
    </div>
  );
}
