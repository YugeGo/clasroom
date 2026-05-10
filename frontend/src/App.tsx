/**
 * App — 主布局：智能对话 + 浏览查找 + 快捷查询 + 周课表
 */
import { FC, useCallback, useRef, useEffect, useState } from "react";
import { ChatBubble } from "./components/ChatBubble";
import { ChatInput } from "./components/ChatInput";
import { BrowsePanel } from "./components/BrowsePanel";
import { ScheduleModal } from "./components/ScheduleModal";
import { useChatStore, useCurrentSession } from "./store/chatStore";
import { groupRooms } from "./api/chat";
import { localSendChatMessageAI } from "./api/local-engine";
import { Sun, Moon, Search, Sparkles } from "lucide-react";

type Mode = "chat" | "browse";

const App: FC = () => {
  const [mode, setMode] = useState<Mode>("chat");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof localStorage !== "undefined" && localStorage.getItem("theme")) {
      return localStorage.getItem("theme") as "light" | "dark";
    }
    if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  });

  // 周课表弹窗状态
  const [scheduleRoom, setScheduleRoom] = useState<{ roomName: string; campus: string } | null>(null);

  const currentSession = useCurrentSession();
  const addMessage = useChatStore((s) => s.addMessage);
  const updateLastMessage = useChatStore((s) => s.updateLastMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentSession?.messages]);

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  const handleSend = useCallback(
    async (message: string) => {
      if (!currentSession) return;

      addMessage({ type: "user", content: message });
      addMessage({ type: "result", content: "", groups: [] });
      setStreaming(true);

      useChatStore.setState((s) => ({
        sessions: s.sessions.map((ses) =>
          ses.id === s.currentSessionId
            ? { ...ses, title: message.length > 24 ? message.slice(0, 24) + "..." : message }
            : ses
        ),
      }));

      try {
        const data = await localSendChatMessageAI(message);
        const groups = groupRooms(data.rooms);
        const params = data.params as any;

        const parts: string[] = [];
        if (params.campus) parts.push(params.campus);
        if (params.building) parts.push(params.building);
        if (params.room) parts.push(params.room);
        parts.push(params.day_of_week);
        const summary = `查询条件：${parts.join(" · ")} · ${data.count} 间空教室`;

        if (data.count === 0) {
          const hint = params.room
            ? `「${params.room}」在${params.day_of_week}没有空闲时段`
            : params.building
              ? `「${params.building}」当前时段没有空闲教室`
              : "当前时段没有找到空教室，试试换个时间或校区？";
          updateLastMessage({ type: "result", content: `${summary}\n\n${hint}`, groups: [] });
        } else {
          // 有 AI 总结则显示
          const displayContent = data.summary ? `${summary}\n\n${data.summary}` : summary;
          updateLastMessage({ type: "result", content: displayContent, groups, params });
        }
      } catch (err: any) {
        updateLastMessage({ type: "result", content: `出错了：${err.message}`, groups: [] });
      } finally {
        setStreaming(false);
      }
    },
    [currentSession, addMessage, updateLastMessage, setStreaming]
  );

  // 浏览模式结果留在浏览面板内，不推到对话
  const handleBrowseResult = useCallback(() => {}, []);

  const handleScheduleClick = useCallback((roomName: string, campus: string) => {
    setScheduleRoom({ roomName, campus });
  }, []);

  return (
    <div className="flex h-screen h-dvh overflow-hidden transition-colors duration-300 bg-[#f5f5f7] dark:bg-[#09090b] text-gray-900 dark:text-zinc-300">
      {/* 背景装饰 */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/[0.05] dark:bg-blue-500/[0.03] blur-[100px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-500/[0.05] dark:bg-violet-500/[0.03] blur-[100px]" />
      </div>

      {/* 主区域 */}
      <div className="relative z-10 flex-1 flex flex-col min-w-0 max-w-4xl mx-auto w-full border-x border-gray-200/50 dark:border-zinc-800/30 bg-white/30 dark:bg-zinc-950/30 shadow-2xl shadow-black/5 dark:shadow-none">
        {/* 顶部 */}
        <header className="border-b border-gray-200/80 dark:border-zinc-800/50 bg-white/70 dark:bg-zinc-950/80 backdrop-blur-xl px-6 py-3 flex items-center justify-between transition-colors duration-300 shrink-0">
          {/* 品牌 */}
          <div className="flex items-center gap-2 mr-4">
            <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-zinc-800 flex items-center justify-center border border-gray-200/80 dark:border-zinc-700/50 shadow-sm transition-colors duration-300">
              <Search size={16} className="text-blue-500 dark:text-zinc-300" />
            </div>
            <h1 className="font-semibold text-gray-900 dark:text-zinc-100 text-[15px] tracking-tight hidden sm:block">空教室狙击手</h1>
          </div>

          {/* 模式标签 */}
          <div className="flex bg-gray-100 dark:bg-zinc-900/50 border border-gray-200/50 dark:border-zinc-800/50 rounded-lg p-1 shadow-sm transition-colors duration-300 mx-auto">
            <button
              onClick={() => setMode("chat")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-1.5 ${
                mode === "chat"
                  ? "bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 shadow-sm"
                  : "text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300 hover:bg-gray-200/50 dark:hover:bg-zinc-800/30"
              }`}
            >
              <Sparkles size={14} />
              智能对话
            </button>
            <button
              onClick={() => setMode("browse")}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
                mode === "browse"
                  ? "bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 shadow-sm"
                  : "text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300 hover:bg-gray-200/50 dark:hover:bg-zinc-800/30"
              }`}
            >
              浏览查找
            </button>
          </div>

          {/* 主题切换 */}
          <div className="flex items-center ml-4">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-gray-100 dark:bg-zinc-800/50 text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 hover:bg-gray-200 dark:hover:bg-zinc-700/50 transition-all duration-200 shadow-sm dark:shadow-none"
              title={theme === "dark" ? "切换到浅色模式" : "切换到深色模式"}
            >
              <span className="block transition-transform duration-300 hover:rotate-12">
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </span>
            </button>
          </div>
        </header>

        {/* 内容区 */}
        {mode === "chat" ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto px-4 py-6 sm:py-8">
              <div className="max-w-3xl mx-auto space-y-6">
                {currentSession?.messages.map((msg) => (
                  <ChatBubble key={msg.id} message={msg} onScheduleClick={handleScheduleClick} />
                ))}
                <div ref={messagesEndRef} className="h-4" />
              </div>
            </div>

            {/* 输入区域 */}
            <div className="shrink-0">
              <ChatInput onSend={handleSend} disabled={isStreaming} />
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-8">
            <div className="max-w-4xl mx-auto">
              <BrowsePanel onQueryResult={handleBrowseResult} onScheduleClick={handleScheduleClick} />
            </div>
          </div>
        )}
      </div>

      {/* 周课表弹窗 */}
      {scheduleRoom && (
        <ScheduleModal
          roomName={scheduleRoom.roomName}
          campus={scheduleRoom.campus}
          onClose={() => setScheduleRoom(null)}
        />
      )}
    </div>
  );
};

export default App;
