"use client";
import { useState, useRef, useEffect } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Send, Bot, User, Loader2, Trash2, TrendingUp } from "lucide-react";

interface Message {
  id:      string;
  role:    "user" | "assistant";
  content: string;
  time:    string;
}

const SUGGESTIONS = [
  "What is a moving average crossover strategy?",
  "Explain RSI and how to use it for trading",
  "What are the best intraday trading strategies for NIFTY?",
  "How do I manage risk in algo trading?",
  "Explain Bollinger Bands with an example",
  "What is VWAP and how traders use it?",
];

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id:      "welcome",
      role:    "assistant",
      content: "Hi! I'm your AI trading assistant. Ask me anything about markets, strategies, technical analysis, or how to use TradeAI.",
      time:    new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = {
      id:      Date.now().toString(),
      role:    "user",
      content: text.trim(),
      time:    new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // Call backend sentiment/strategy endpoint as AI proxy
      // Falls back to a local response if backend unavailable
      const response = await api.post("/strategy/generate", {
        prompt:      text,
        symbols:     ["NIFTY50"],
        timeframe:   "1d",
        ai_provider: "claude",
      }).catch(() => null);

      let content = "";
      if (response?.data) {
        const d = response.data;
        content = `**${d.name || "Analysis"}**\n\n${d.description || ""}\n\n`;
        if (d.entry_logic)  content += `**Entry:** ${d.entry_logic}\n\n`;
        if (d.exit_logic)   content += `**Exit:** ${d.exit_logic}\n\n`;
        if (d.risk_rules)   content += `**Risk:** ${d.risk_rules}`;
        if (d.explanation)  content = d.explanation;
      } else {
        content = "I'm here to help with trading questions! Ask me about strategies, technical indicators, risk management, or market analysis. You can also use the **AI Strategy Builder** to generate complete trading strategies.";
      }

      setMessages((prev) => [...prev, {
        id:      Date.now().toString() + "_ai",
        role:    "assistant",
        content,
        time:    new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
      }]);
    } catch {
      setMessages((prev) => [...prev, {
        id:      Date.now().toString() + "_err",
        role:    "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        time:    new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-7rem)] max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-white font-bold text-lg">AI Trading Assistant</h2>
              <p className="text-gray-400 text-xs">Powered by Claude · Ask anything about markets</p>
            </div>
          </div>
          <button onClick={() => setMessages([{
            id: "welcome", role: "assistant",
            content: "Hi! I'm your AI trading assistant. Ask me anything!",
            time: new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
          }])}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 hover:text-white rounded-xl text-xs font-medium transition-all">
            <Trash2 className="h-3.5 w-3.5" /> Clear
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
              {/* Avatar */}
              <div className={cn("h-8 w-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1",
                msg.role === "user" ? "bg-blue-600" : "bg-gradient-to-br from-blue-600 to-purple-600")}>
                {msg.role === "user"
                  ? <User className="h-4 w-4 text-white" />
                  : <Bot  className="h-4 w-4 text-white" />}
              </div>

              {/* Bubble */}
              <div className={cn("max-w-[75%] rounded-2xl px-4 py-3",
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-tr-sm"
                  : "bg-gray-900 border border-gray-800 text-gray-200 rounded-tl-sm")}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                <p className={cn("text-[10px] mt-1.5",
                  msg.role === "user" ? "text-blue-200 text-right" : "text-gray-600")}>
                  {msg.time}
                </p>
              </div>
            </div>
          ))}

          {/* Loading bubble */}
          {loading && (
            <div className="flex gap-3">
              <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <div className="bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex items-center gap-1.5">
                  {[0,1,2].map((i) => (
                    <div key={i} className="h-2 w-2 rounded-full bg-blue-400 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggestions */}
        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-2 mb-3 flex-shrink-0">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => sendMessage(s)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-600 text-gray-400 hover:text-white rounded-xl text-xs transition-all">
                <TrendingUp className="h-3 w-3 text-blue-400" />
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="flex gap-3 flex-shrink-0">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
            placeholder="Ask about strategies, indicators, risk management..."
            disabled={loading}
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
          />
          <button onClick={() => sendMessage(input)} disabled={!input.trim() || loading}
            className="h-12 w-12 flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all disabled:opacity-40 flex-shrink-0">
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
}
