/**
 * ChatBubble — 聊天气泡（用户 / AI / 结果卡片）
 */
import { FC } from "react";
import { User, Bot, Loader2 } from "lucide-react";
import type { ChatMessage } from "../store/chatStore";
import { RoomCard } from "./RoomCard";

interface Props {
  message: ChatMessage;
  onScheduleClick?: (roomName: string, campus: string) => void;
}

export const ChatBubble: FC<Props> = ({ message, onScheduleClick }) => {
  const { type, content, groups } = message;

  if (type === "user") {
    return (
      <div className="flex justify-end animate-fade-in mb-6">
        <div className="max-w-[75%] bg-blue-500 text-white dark:bg-zinc-800 dark:text-zinc-100 rounded-2xl rounded-tr-sm px-5 py-3 shadow-[0_2px_10px_rgba(59,130,246,0.15)] dark:shadow-sm dark:border dark:border-zinc-700/50 hover:shadow-[0_4px_12px_rgba(59,130,246,0.2)] dark:hover:shadow-md transition-shadow duration-300">
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    );
  }

  if (type === "result") {
    if (!groups || groups.length === 0) {
      return (
        <div className="animate-fade-in mb-6 flex gap-4 group">
          <div className="w-8 h-8 rounded-full bg-white dark:bg-zinc-800 flex items-center justify-center flex-shrink-0 border border-gray-200 dark:border-zinc-700/50 shadow-sm mt-1 transition-transform duration-300 group-hover:scale-105">
            <Bot size={16} className="text-gray-600 dark:text-zinc-300" />
          </div>
          <div className="flex-1 max-w-[85%] bg-white dark:bg-transparent border border-gray-100 dark:border-transparent rounded-2xl rounded-tl-sm px-5 py-3 shadow-sm dark:shadow-none dark:p-0">
            <p className="text-gray-700 dark:text-zinc-300 text-[15px] whitespace-pre-wrap leading-relaxed">
              {content || "当前时间段没有找到空教室，试试换个时间或校区？"}
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="animate-fade-in mb-6 flex gap-4 group">
        <div className="w-8 h-8 rounded-full bg-white dark:bg-zinc-800 flex items-center justify-center flex-shrink-0 border border-gray-200 dark:border-zinc-700/50 shadow-sm mt-1 transition-transform duration-300 group-hover:scale-105">
          <Bot size={16} className="text-gray-600 dark:text-zinc-300" />
        </div>
        <div className="flex-1 min-w-0">
          {/* 头部摘要 */}
          <div className="flex items-center gap-3 mb-4">
            <span className="text-[15px] font-medium text-gray-800 dark:text-zinc-200">
              找到 <span className="text-blue-500 dark:text-blue-400 font-semibold">{groups.length}</span> 间空教室
            </span>
            <span className="text-xs text-gray-400 dark:text-zinc-500 font-medium">
              {new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>

          {/* 教室卡片列表 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            {groups.map((room) => (
              <RoomCard key={`${room.campus}-${room.room_name}`} room={room} onScheduleClick={onScheduleClick} />
            ))}
          </div>

          {/* 底部提示 */}
          {content && (
            <div className="inline-block bg-gray-50 dark:bg-zinc-900/50 border border-gray-200 dark:border-zinc-800/80 rounded-xl px-4 py-3 shadow-sm dark:shadow-none">
              <p className="text-gray-600 dark:text-zinc-400 text-sm whitespace-pre-wrap leading-relaxed">
                {content}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // type === "ai" — 纯文本回复（含 Markdown 风格的标题）
  return (
    <div className="animate-fade-in mb-6 flex gap-4 group">
      <div className="w-8 h-8 rounded-full bg-white dark:bg-zinc-800 flex items-center justify-center flex-shrink-0 border border-gray-200 dark:border-zinc-700/50 shadow-sm mt-1 transition-transform duration-300 group-hover:scale-105">
        <Bot size={16} className="text-gray-600 dark:text-zinc-300" />
      </div>
      <div className="flex-1 max-w-[85%] bg-white dark:bg-transparent border border-gray-100 dark:border-transparent rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm dark:shadow-none dark:p-0 text-[15px] text-gray-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap transition-colors duration-300">
        {content.split("\n").map((line, i) => {
          if (line.startsWith("# ")) {
            return (
              <p key={i} className="text-gray-900 dark:text-zinc-100 font-semibold text-lg mb-3 mt-4 first:mt-0">
                {line.slice(2)}
              </p>
            );
          }
          if (line.startsWith("- ")) {
            return (
              <div key={i} className="flex gap-2 mb-1.5 ml-1">
                <span className="text-gray-400 dark:text-zinc-500 mt-1.5">•</span>
                <span className="text-gray-700 dark:text-zinc-300">{line.slice(2)}</span>
              </div>
            );
          }
          if (line.trim() === "") {
            return <div key={i} className="h-2" />;
          }
          return (
            <p key={i} className="mb-2 last:mb-0">
              {line}
            </p>
          );
        })}
      </div>
    </div>
  );
};
