"use client";
import { useEffect, useRef, useState } from "react";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>(
    []
  );
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(
        "https://my-ai-fullstack-app-production.up.railway.app/chat",
        {
          // 👈 确保这里是你 Railway 的地址
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: input, session_id: "user_123" }),
        }
      );

      const data = await res.json();

      // 后端返回的内容
      const botResponse = data.response;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: botResponse },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "系统繁忙，请稍后再试。" },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="p-4 bg-gray-800 shadow-md">
        <h1 className="text-xl font-bold text-green-400 font-mono">
          My AI Assistant (Writer & Painter)
        </h1>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            <p>👋 你好！我是你的全栈 AI 助手。</p>
            <p className="text-sm mt-2">试试问我时间，或者说 "给我画一只猫"</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg ${
                msg.role === "user"
                  ? "bg-green-600 text-white"
                  : "bg-gray-700 text-gray-200"
              }`}
            >
              {/* 👇👇👇 核心修改：判断是不是图片链接 👇👇👇 */}
              {msg.content.startsWith("IMAGE_URL:") ? (
                <div>
                  <p className="mb-2 text-sm text-gray-400">
                    🎨 图片生成成功：
                  </p>
                  <img
                    src={msg.content.replace("IMAGE_URL:", "")}
                    alt="AI Generated"
                    className="rounded-md w-full max-w-sm border border-gray-600"
                  />
                </div>
              ) : (
                msg.content
              )}
              {/* 👆👆👆 修改结束 👆👆👆 */}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="text-green-400 text-sm ml-2">AI 正在思考/作画...</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-gray-800 border-t border-gray-700">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="请输入你的问题... (试着说: 画一只赛博朋克的猫)"
            className="flex-1 p-3 rounded-lg bg-gray-900 border border-gray-600 focus:outline-none focus:border-green-500 text-white"
          />
          <button
            onClick={sendMessage}
            disabled={isLoading}
            className="px-6 py-3 bg-green-600 hover:bg-green-700 rounded-lg font-bold transition-colors disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
