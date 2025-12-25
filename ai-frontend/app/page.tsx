"use client"; // 这一行必须在最上面，代表这是个客户端组件
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Home() {
  // 定义状态：输入框的内容、聊天记录、是否正在加载
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(false);

  const [sessionId, setSessionId] = useState("");

  // === 新增：页面加载时，找后端要历史记录 ===
  useEffect(() => {
    // 1. 先从浏览器缓存里找身份证
    let myId = localStorage.getItem("chat_session_id");
    if (!myId) {
      myId = Date.now().toString(); // 没身份证就现办一个
      localStorage.setItem("chat_session_id", myId);
    }
    setSessionId(myId);

    // 2. 拿着身份证去问后端要之前的聊天记录
    const fetchHistory = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/history/${myId}`);
        const data = await res.json();
        // 如果后端真给了记录，就显示在屏幕上
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        }
      } catch (error) {
        console.error("加载历史失败:", error);
      }
    };
    fetchHistory();
  }, []);

  // 发送消息的函数
  // ... 上面的 import 和 state 定义不变 ...

  const sendMessage = async () => {
    if (!input.trim()) return;

    // 1. 设置用户消息
    const userMessage = { role: "user", content: input };
    const newHistory = [...messages, userMessage];

    // 2. 先把用户消息放上去，并放一个“空的”AI消息占位
    setMessages([...newHistory, { role: "assistant", content: "" }]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newHistory,
          sessionId: sessionId, // <--- 【修改这里】加上这行，带上身份证
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) return;

      // === ✨ 核心修改开始：丝滑打字机缓冲逻辑 ===

      let fullRawText = ""; // 仓库：存放后端发来的所有原始文本
      let displayedText = ""; // 屏幕：当前屏幕上已经显示的文本
      let isDone = false; // 标记：网络传输是否结束

      // A. 启动一个定时器，每 30ms 刷新一次屏幕（这就是 30FPS 的丝滑感）
      const timer = setInterval(() => {
        // 如果“仓库里的字”比“屏幕上的字”多，就取出一个字显示
        if (displayedText.length < fullRawText.length) {
          // 取出下一个要显示的字
          const char = fullRawText[displayedText.length];
          displayedText += char;

          // 更新 React 界面
          setMessages((prev) => {
            const newMsgs = [...prev];
            // 找到最后一条消息（就是那个空的 assistant）
            const lastMsg = { ...newMsgs[newMsgs.length - 1] };
            lastMsg.content = displayedText; // 更新内容
            newMsgs[newMsgs.length - 1] = lastMsg;
            return newMsgs;
          });
        }
        // 如果网络传完了，而且屏幕上也显示完了，就停下来
        else if (isDone) {
          clearInterval(timer);
          setIsLoading(false);
        }
      }, 20); // <--- 这里调速度：30ms 比较适中，越小越快

      // B. 网络接收循环 (只负责收货，不负责显示)
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          isDone = true;
          break;
        }
        // 解码数据
        const chunk = decoder.decode(value, { stream: true });
        // 把收到的货直接扔进仓库，完全不管界面刷新
        fullRawText += chunk;
      }
      // === ✨ 核心修改结束 ===
    } catch (error) {
      console.error("Error:", error);
      setIsLoading(false);
    }
  };
  // ... 下面的 return HTML 代码不变 ...

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-4 bg-gray-900 text-white">
      {/* 标题栏 */}
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm lg:flex border-b border-gray-700 pb-4">
        <h1 className="text-2xl font-bold text-green-400">My AI Assistant</h1>
        <p>Powered by Next.js + Python</p>
      </div>

      {/* 聊天记录区域 */}
      <div className="flex-1 w-full max-w-2xl overflow-y-auto my-4 space-y-4 p-4 rounded-lg bg-gray-800">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            👋 你好！我是你的专属 AI 助手，问我点什么吧？
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
              className={`max-w-[80%] rounded-lg p-3 ${
                msg.role === "user"
                  ? "bg-green-600 text-white"
                  : "bg-gray-700 text-gray-100"
              }`}
            >
              <strong>{msg.role === "user" ? "我" : "AI"}:</strong>
              <div className="prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="text-green-400 animate-pulse">AI 正在思考...</div>
        )}
      </div>

      {/* 输入框区域 */}
      <div className="w-full max-w-2xl flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          className="flex-1 p-3 rounded-lg bg-gray-700 border border-gray-600 focus:outline-none focus:border-green-500"
          placeholder="请输入你的问题..."
        />
        <button
          onClick={sendMessage}
          disabled={isLoading}
          className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold disabled:opacity-50"
        >
          发送
        </button>
      </div>
    </main>
  );
}
