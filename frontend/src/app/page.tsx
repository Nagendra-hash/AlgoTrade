// Path: frontend/src/app/page.tsx
import Link from "next/link";
import { TrendingUp, Bot, Shield, Zap, BarChart2, ArrowRight, Bell } from "lucide-react";

const FEATURES = [
  { icon: Bot,       title: "AI Strategy Builder",    desc: "Describe in plain English — AI generates complete Python trading logic instantly.", color: "text-blue-400",   bg: "bg-blue-500/10" },
  { icon: TrendingUp,title: "Live Market Data",       desc: "Real-time WebSocket streaming with professional TradingView-style charts.",        color: "text-green-400",  bg: "bg-green-500/10" },
  { icon: BarChart2, title: "Advanced Backtesting",   desc: "Test strategies on years of data. Get Sharpe ratio, drawdown, win rate and more.", color: "text-purple-400", bg: "bg-purple-500/10" },
  { icon: Shield,    title: "Risk Management",        desc: "Built-in stop-loss, take-profit, and trailing stops. Never blow your account.",     color: "text-orange-400", bg: "bg-orange-500/10" },
  { icon: Bell,      title: "AI Alerts & News",       desc: "Real-time price alerts with AI sentiment analysis across 15+ news sources.",        color: "text-yellow-400", bg: "bg-yellow-500/10" },
  { icon: Zap,       title: "Auto Trading",           desc: "Deploy strategies to live markets with one click. Monitor 24/7.",                  color: "text-pink-400",   bg: "bg-pink-500/10" },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <TrendingUp className="h-4 w-4 text-white" />
            </div>
            <span className="text-xl font-black bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">TradeAI</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-gray-400 hover:text-white text-sm transition-colors">Login</Link>
            <Link href="/signup" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all flex items-center gap-1.5">
              Get Started <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-24 pb-20 px-4 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 text-sm font-semibold mb-6">
            🚀 AI-Powered Algo Trading Platform
          </div>
          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            Trade Smarter with{" "}
            <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Artificial Intelligence
            </span>
          </h1>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Build, test, and deploy AI-powered trading strategies for Indian markets. Connect Angel One & Zerodha. Trade automatically.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/signup" className="px-8 py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2 text-base shadow-lg shadow-blue-500/20">
              Start Free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/login" className="px-8 py-3.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl font-semibold transition-all text-base">
              Login to Dashboard
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto mt-16">
          {[["50+","Strategies"],["99.9%","Uptime"],["<10ms","Latency"],["2","Brokers"]].map(([v,l]) => (
            <div key={l} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-2xl font-black text-white">{v}</p>
              <p className="text-gray-400 text-sm">{l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Everything you need to trade algorithmically</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 hover:border-gray-700 transition-all group">
                  <div className={`${f.bg} h-10 w-10 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    <Icon className={`h-5 w-5 ${f.color}`} />
                  </div>
                  <h3 className="text-white font-semibold mb-2">{f.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-400" />
            <span className="font-bold text-gray-300">TradeAI</span>
          </div>
          <p className="text-gray-500 text-sm">© 2024 TradeAI. Not financial advice. Trading involves risk.</p>
        </div>
      </footer>
    </div>
  );
}
