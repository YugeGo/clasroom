/**
 * ChatInput — 消息输入框 + 发送按钮
 * 优化移动端适配：大触摸目标 + 按钮点击兜底
 */
import { FC, FormEvent, useState, useRef, useEffect, useCallback } from "react";
import { Send, Loader2 } from "lucide-react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

export const ChatInput: FC<Props> = ({ onSend, disabled }) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 140) + "px";
    }
  }, [text]);

  const doSend = useCallback(() => {
    const msg = text.trim();
    if (!msg || disabled) return;
    onSend(msg);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, disabled, onSend]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    doSend();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  };

  return (
    <div className="bg-gradient-to-t from-[#f5f5f7] via-[#f5f5f7]/80 dark:from-[#09090b] dark:via-[#09090b]/80 to-transparent pt-4 pb-4 sm:pt-6 sm:pb-6 px-3 sm:px-4 transition-colors duration-300">
      <form
        onSubmit={handleSubmit}
        className="max-w-3xl mx-auto relative shadow-sm hover:shadow-md transition-shadow duration-300 rounded-2xl"
      >
        <div className="relative flex items-end bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-2xl overflow-hidden focus-within:border-blue-400 dark:focus-within:border-zinc-700 focus-within:ring-1 focus-within:ring-blue-400 dark:focus-within:ring-zinc-700 transition-all duration-200 shadow-[0_4px_20px_rgba(0,0,0,0.04)] dark:shadow-none">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述你的需求，例如：下午舜耕有空教室吗..."
            rows={1}
            disabled={disabled}
            inputMode="text"
            enterKeyHint="send"
            className="flex-1 max-h-40 min-h-[52px] w-full resize-none bg-transparent px-4 py-3.5 sm:py-3.5 text-[16px] sm:text-[15px] text-gray-900 dark:text-zinc-200 placeholder-gray-400 dark:placeholder-zinc-500 outline-none disabled:opacity-50"
          />

          <div className="p-1.5 sm:p-2 flex-shrink-0">
            <button
              type="submit"
              onClick={(e) => { e.preventDefault(); doSend(); }}
              disabled={!text.trim() || disabled}
              className="w-11 h-11 sm:w-9 sm:h-9 rounded-xl bg-blue-500 dark:bg-white text-white dark:text-black flex items-center justify-center hover:bg-blue-600 dark:hover:bg-zinc-200 disabled:bg-gray-100 disabled:text-gray-400 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-500 disabled:cursor-not-allowed transition-all duration-200 shadow-sm hover:scale-105 active:scale-95 disabled:hover:scale-100 touch-manipulation"
              aria-label="发送消息"
            >
              {disabled ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <Send size={18} className="ml-0.5" />
              )}
            </button>
          </div>
        </div>
        <p className="text-[11px] text-gray-400 dark:text-zinc-500 text-center mt-2 sm:mt-3 font-medium transition-colors duration-300">
          按 Enter 发送 · 点击按钮发送
        </p>
      </form>
    </div>
  );
};
