"use client";
// Path: frontend/src/app/strategy/page.tsx
import { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useGenerateAndSaveStrategy, useStrategies, useDeployStrategy, useDeleteStrategy } from "@/hooks/useStrategies";
import { cn } from "@/lib/utils";
import { Sparkles, Play, Trash2, BookOpen, Code2, Settings2, Bot, Loader2, RotateCcw, CheckCircle2, AlertCircle, ChevronRight } from "lucide-react";
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const TEMPLATES = [
  { label: "MA Crossover",    prompt: "Create a moving average crossover strategy using 20 and 50 period EMAs for NIFTY 50 with volume confirmation" },
  { label: "RSI + MACD",      prompt: "Build an RSI and MACD combined strategy. Enter when RSI is oversold and MACD shows bullish crossover" },
  { label: "Bollinger Bands", prompt: "Create a Bollinger Bands mean reversion strategy. Buy when price touches lower band with increasing volume" },
  { label: "Breakout",        prompt: "Build a 20-day high breakout strategy with 2x average volume confirmation" },
  { label: "Supertrend",      prompt: "Create a Supertrend indicator strategy with ATR period 10 and multiplier 3, add RSI filter" },
  { label: "VWAP Intraday",   prompt: "Build an intraday VWAP strategy. Buy when price crosses above VWAP in the first hour with tight stop loss" },
];

const AI_PROVIDERS = [
  { id: "claude",  label: "Claude",  desc: "Best reasoning" },
  { id: "openai",  label: "GPT-4o",  desc: "Fast & reliable" },
  { id: "ollama",  label: "Ollama",  desc: "Free, local AI" },
];

const TIMEFRAMES = ["1m","5m","15m","30m","1h","1d","1w"];
const SYMBOLS    = ["NIFTY50","BANKNIFTY","RELIANCE","TCS","INFY","HDFCBANK","SBIN","SENSEX"];

export default function StrategyPage() {
  const [prompt,     setPrompt]     = useState("");
  const [provider,   setProvider]   = useState("claude");
  const [timeframe,  setTimeframe]  = useState("1d");
  const [symbols,    setSymbols]    = useState(["NIFTY50"]);
  const [activeTab,  setActiveTab]  = useState<"logic"|"code"|"params"|"explain">("logic");
  const [generated,  setGenerated]  = useState<Record<string,unknown> | null>(null);
  const [editedCode, setEditedCode] = useState("");

  const generateSave = useGenerateAndSaveStrategy();
  const { data: strategies = [] } = useStrategies();
  const deploy  = useDeployStrategy();
  const delStrat= useDeleteStrategy();

  const toggleSymbol = (s: string) =>
    setSymbols((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const handleGenerate = async () => {
    const result = await generateSave.mutateAsync({ prompt, symbols, timeframe, ai_provider: provider });
    setGenerated(result as unknown as Record<string,unknown>);
    setEditedCode((result as { python_code?: string }).python_code ?? "");
    setActiveTab("logic");
  };

  const tabs = [
    { id: "logic",   label: "Strategy Logic", icon: BookOpen },
    { id: "code",    label: "Python Code",    icon: Code2    },
    { id: "params",  label: "Parameters",     icon: Settings2},
    { id: "explain", label: "Explanation",    icon: Bot      },
  ];

  return (
    <DashboardLayout>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: Config */}
        <div className="xl:col-span-1 space-y-4">
          {/* AI Provider */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
            <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">AI Provider</p>
            <div className="grid grid-cols-3 gap-2">
              {AI_PROVIDERS.map((p) => (
                <button key={p.id} onClick={() => setProvider(p.id)}
                  className={cn("flex flex-col items-center py-2.5 rounded-xl border text-xs transition-all",
                    provider === p.id ? "bg-blue-600/20 border-blue-500 text-blue-400" : "border-gray-700 text-gray-400 hover:border-gray-600")}>
                  <Bot className="h-4 w-4 mb-1" />
                  <span className="font-bold">{p.label}</span>
                  <span className="text-[10px] text-gray-500">{p.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Symbols */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
            <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">Target Symbols</p>
            <div className="flex flex-wrap gap-2">
              {SYMBOLS.map((s) => (
                <button key={s} onClick={() => toggleSymbol(s)}
                  className={cn("px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all",
                    symbols.includes(s) ? "bg-blue-600/20 border-blue-500/40 text-blue-400" : "border-gray-700 text-gray-500 hover:text-gray-300")}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
            <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">Timeframe</p>
            <div className="flex flex-wrap gap-2">
              {TIMEFRAMES.map((tf) => (
                <button key={tf} onClick={() => setTimeframe(tf)}
                  className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all",
                    timeframe === tf ? "bg-purple-600/20 border-purple-500/40 text-purple-400" : "border-gray-700 text-gray-500 hover:text-gray-300")}>
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Templates */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
            <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">Quick Templates</p>
            <div className="space-y-1.5">
              {TEMPLATES.map((t) => (
                <button key={t.label} onClick={() => setPrompt(t.prompt)}
                  className="w-full flex items-center gap-2 text-left px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors">
                  <ChevronRight className="h-3 w-3 text-blue-400 flex-shrink-0" />
                  <span className="text-gray-300 text-xs">{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Saved strategies */}
          {strategies.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
              <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">
                My Strategies ({strategies.length})
              </p>
              <div className="space-y-2 max-h-52 overflow-y-auto">
                {strategies.map((s) => (
                  <div key={s.id} className="flex items-center justify-between p-2.5 bg-gray-800 rounded-xl">
                    <div className="min-w-0">
                      <p className="text-white text-xs font-semibold truncate">{s.name}</p>
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded border",
                        s.is_paper_active ? "bg-green-400/10 text-green-400 border-green-500/20" : "bg-gray-700 text-gray-500 border-gray-600")}>
                        {s.is_paper_active ? "● Live Paper" : s.status}
                      </span>
                    </div>
                    <div className="flex gap-1 flex-shrink-0 ml-2">
                      {!s.is_paper_active && (
                        <button onClick={() => deploy.mutate({ id: s.id, mode: "paper" })} title="Deploy to paper"
                          className="h-6 w-6 flex items-center justify-center text-green-400 hover:bg-green-400/10 rounded-lg transition-all">
                          <Play className="h-3 w-3" />
                        </button>
                      )}
                      <button onClick={() => delStrat.mutate(s.id)} title="Delete"
                        className="h-6 w-6 flex items-center justify-center text-red-400 hover:bg-red-400/10 rounded-lg transition-all">
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Generator */}
        <div className="xl:col-span-2 space-y-4">
          {/* Prompt input */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="h-5 w-5 text-purple-400" />
              <h3 className="text-white font-bold">AI Strategy Generator</h3>
              <span className="ml-auto text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2.5 py-0.5 rounded-full font-semibold">
                Powered by {provider === "claude" ? "Claude" : provider === "openai" ? "GPT-4o" : "Ollama"}
              </span>
            </div>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5}
              placeholder={`Describe your trading strategy in plain English...\n\nExamples:\n• "Create a momentum strategy using RSI and volume for NIFTY"\n• "Build an intraday gap-and-go strategy with tight stop losses"\n• "Design a swing trading strategy using support/resistance"`}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl text-white text-sm p-4 placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 transition-colors leading-relaxed" />
            <div className="flex items-center justify-between mt-3">
              <p className="text-gray-600 text-xs">{prompt.length}/2000</p>
              <div className="flex gap-2">
                <button onClick={() => setPrompt("")} disabled={!prompt}
                  className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 rounded-xl text-xs font-medium transition-all disabled:opacity-40">
                  <RotateCcw className="h-3.5 w-3.5" /> Clear
                </button>
                <button onClick={handleGenerate} disabled={!prompt || generateSave.isPending || prompt.length < 10}
                  className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50">
                  {generateSave.isPending
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</>
                    : <><Sparkles className="h-4 w-4" /> Generate & Save</>}
                </button>
              </div>
            </div>
          </div>

          {/* Loading */}
          {generateSave.isPending && (
            <div className="bg-gray-900 border border-blue-500/20 rounded-2xl p-12 text-center">
              <div className="h-16 w-16 rounded-2xl bg-blue-600/10 flex items-center justify-center mx-auto mb-4 relative">
                <Sparkles className="h-8 w-8 text-blue-400" />
                <div className="absolute inset-0 rounded-2xl border-2 border-blue-500/30 animate-ping" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">AI is thinking...</h3>
              <p className="text-gray-400 text-sm">Generating entry/exit logic, risk management, and Python code</p>
              <div className="flex items-center justify-center gap-1.5 mt-4">
                {[0,1,2,3,4].map((i) => (
                  <div key={i} className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: `${i*0.12}s` }} />
                ))}
              </div>
            </div>
          )}

          {/* Generated result */}
          {generated && !generateSave.isPending && (
            <div className="bg-gray-900 border border-blue-500/20 rounded-2xl overflow-hidden">
              {/* Strategy header */}
              <div className="p-5 border-b border-gray-800 bg-gradient-to-r from-blue-600/10 to-purple-600/10">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <CheckCircle2 className="h-4 w-4 text-green-400" />
                      <h3 className="text-white font-black text-lg">{String(generated.name)}</h3>
                    </div>
                    <p className="text-gray-400 text-sm">{String(generated.description)}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xs px-2 py-0.5 rounded-full capitalize">
                        {String(generated.strategy_type).replace("_"," ")}
                      </span>
                      {(generated.tags as string[] || []).slice(0,3).map((tag) => (
                        <span key={tag} className="bg-gray-700 text-gray-400 border border-gray-600 text-xs px-2 py-0.5 rounded-full">#{tag}</span>
                      ))}
                    </div>
                    {(generated.indicators as string[] || []).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        <span className="text-gray-500 text-xs">Indicators:</span>
                        {(generated.indicators as string[]).map((ind) => (
                          <span key={ind} className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-2 py-0.5 rounded-full">{ind}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <span className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs px-2.5 py-1 rounded-full font-semibold flex-shrink-0">✅ Saved</span>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-gray-800 overflow-x-auto">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button key={tab.id} onClick={() => setActiveTab(tab.id as typeof activeTab)}
                      className={cn("flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap",
                        activeTab === tab.id ? "border-blue-500 text-blue-400" : "border-transparent text-gray-500 hover:text-gray-300")}>
                      <Icon className="h-3.5 w-3.5" />{tab.label}
                    </button>
                  );
                })}
              </div>

              {/* Tab content */}
              <div className="p-5">
                {activeTab === "logic" && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { title: "Entry Conditions", content: String(generated.entry_logic ?? ""), color: "text-green-400" },
                      { title: "Exit Conditions",  content: String(generated.exit_logic  ?? ""), color: "text-red-400"   },
                      { title: "Risk Management",  content: String(generated.risk_rules  ?? ""), color: "text-blue-400"  },
                    ].map((section) => (
                      <div key={section.title} className="bg-gray-800 rounded-xl p-4">
                        <p className={cn("font-bold text-sm mb-3", section.color)}>{section.title}</p>
                        <div className="space-y-1.5">
                          {section.content.split("\n").filter(Boolean).map((line, i) => (
                            <p key={i} className="text-gray-300 text-xs leading-relaxed">
                              {line.startsWith("-") ? <>· {line.slice(1).trim()}</> : line}
                            </p>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === "code" && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                      <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
                      <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
                      <span className="text-gray-500 text-xs ml-1 font-mono">strategy.py</span>
                    </div>
                    <div className="rounded-xl overflow-hidden border border-gray-700">
                      <MonacoEditor height="400px" language="python" value={editedCode}
                        onChange={(v) => setEditedCode(v ?? "")} theme="vs-dark"
                        options={{ fontSize: 13, minimap: { enabled: false }, scrollBeyondLastLine: false, padding: { top: 12, bottom: 12 }, wordWrap: "on", tabSize: 4 }} />
                    </div>
                  </div>
                )}

                {activeTab === "params" && (
                  <div>
                    <p className="text-gray-400 text-sm mb-4">Fine-tune parameters to customize strategy behavior.</p>
                    {Object.keys(generated.parameters as Record<string, unknown> ?? {}).length === 0 ? (
                      <p className="text-gray-500 text-sm">No tunable parameters for this strategy.</p>
                    ) : (
                      <div className="space-y-4">
                        {Object.entries(generated.parameters as Record<string, { value: number; min: number; max: number; step: number; description: string }>).map(([key, param]) => (
                          <div key={key} className="bg-gray-800 rounded-xl p-4">
                            <div className="flex items-center justify-between mb-2">
                              <div>
                                <p className="text-white font-semibold text-sm capitalize">{key.replace(/_/g," ")}</p>
                                <p className="text-gray-500 text-xs">{param.description}</p>
                              </div>
                              <div className="bg-blue-600/20 border border-blue-500/30 rounded-lg px-3 py-1.5">
                                <span className="text-blue-400 font-black text-lg">{param.value}</span>
                              </div>
                            </div>
                            <input type="range" min={param.min} max={param.max} step={param.step} defaultValue={param.value}
                              className="w-full accent-blue-500" />
                            <div className="flex justify-between text-xs text-gray-600 mt-1">
                              <span>{param.min}</span><span>{param.max}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "explain" && (
                  <div className="bg-gray-800 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-4">
                      <Bot className="h-5 w-5 text-purple-400" />
                      <span className="text-white font-semibold">AI Explanation</span>
                      <span className="bg-purple-500/10 text-purple-400 border border-purple-500/20 text-xs px-2 py-0.5 rounded-full">Beginner Friendly</span>
                    </div>
                    <p className="text-gray-300 text-sm leading-relaxed">{String(generated.explanation)}</p>
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      <p className="text-yellow-400 text-xs font-semibold flex items-center gap-1.5 mb-2">
                        <AlertCircle className="h-3.5 w-3.5" /> Risk Disclaimer
                      </p>
                      <p className="text-gray-500 text-xs leading-relaxed">
                        This strategy is AI-generated and for educational purposes only. Always backtest thoroughly before using real money. Past performance does not guarantee future results.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-gray-800 p-4 flex items-center justify-between gap-3 flex-wrap">
                <p className="text-gray-500 text-xs">Saved to your strategy library ✓</p>
                <div className="flex gap-2">
                  <a href="/backtest" className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-xs font-medium transition-all">
                    📊 Backtest First
                  </a>
                  <button onClick={() => {
                    const s = strategies[0];
                    if (s) deploy.mutate({ id: s.id, mode: "paper" });
                  }} className="flex items-center gap-1.5 px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-xl text-xs font-semibold transition-all">
                    <Play className="h-3.5 w-3.5" /> Deploy to Paper
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!generated && !generateSave.isPending && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-12 text-center">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/20 flex items-center justify-center mx-auto mb-4">
                <Sparkles className="h-8 w-8 text-blue-400" />
              </div>
              <h3 className="text-white font-bold text-lg mb-2">Describe Your Strategy</h3>
              <p className="text-gray-400 text-sm max-w-sm mx-auto leading-relaxed">
                Type any trading idea in plain English and AI will generate complete Python code, entry/exit rules, and risk management — instantly.
              </p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
