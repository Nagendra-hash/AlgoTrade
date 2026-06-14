// ─── All application TypeScript types ───────────────────────
// Path: frontend/src/types/index.ts

// ── User ──────────────────────────────────────────────────────
export interface User {
  id:          string;
  email:       string;
  username:    string;
  full_name:   string | null;
  role:        "admin" | "trader" | "viewer";
  is_active:   boolean;
  is_verified: boolean;
  avatar_url:  string | null;
  created_at:  string;
  last_login:  string | null;
}

export interface TokenResponse {
  access_token:  string;
  refresh_token: string;
  token_type:    string;
  user:          User;
}

// ── Market ────────────────────────────────────────────────────
export interface Quote {
  symbol:     string;
  exchange:   string;
  ltp:        number;
  open:       number;
  high:       number;
  low:        number;
  prev_close: number;
  change:     number;
  change_pct: number;
  volume:     number;
  timestamp:  string;
  source?:   "angel_one" | "zerodha" | "yfinance";  // data source indicator
}

export interface Candle {
  time:   number;
  open:   number;
  high:   number;
  low:    number;
  close:  number;
  volume: number;
}

export interface Instrument {
  symbol:   string;
  name:     string;
  exchange: string;
  sector:   string;
}

// ── Order ─────────────────────────────────────────────────────
export type OrderSide    = "BUY" | "SELL";
export type OrderType    = "MARKET" | "LIMIT" | "STOP_LOSS" | "STOP_LOSS_MARKET";
export type OrderStatus  = "PENDING" | "OPEN" | "COMPLETE" | "CANCELLED" | "REJECTED";
export type ProductType  = "INTRADAY" | "DELIVERY" | "NORMAL";

export interface Order {
  id:              string;
  broker_order_id: string | null;
  symbol:          string;
  exchange:        string;
  side:            OrderSide;
  order_type:      OrderType;
  product_type:    ProductType;
  status:          OrderStatus;
  quantity:        number;
  price:           number | null;
  average_price:   number | null;
  filled_quantity: number | null;
  stop_loss:       number | null;
  take_profit:     number | null;
  is_paper_trade:  string;
  placed_at:       string;
  executed_at:     string | null;
}

export interface PlaceOrderPayload {
  symbol:         string;
  exchange?:      string;
  side:           OrderSide;
  order_type:     OrderType;
  product_type?:  ProductType;
  quantity:       number;
  price?:         number;
  trigger_price?: number;
  stop_loss?:     number;
  take_profit?:   number;
  is_paper_trade?: boolean;
}

// ── Portfolio ─────────────────────────────────────────────────
export interface Holding {
  symbol:         string;
  exchange:       string;
  quantity:       number;
  average_price:  number;
  ltp:            number;
  current_value:  number;
  invested_value: number;
  pnl:            number;
  pnl_pct:        number;
  change_pct:     number;
  sector?:        string;
}

export interface Position {
  symbol:        string;
  exchange:      string;
  quantity:      number;
  average_price: number;
  ltp:           number;
  pnl:           number;
  pnl_pct:       number;
  product_type:  string;
}

export interface PortfolioSummary {
  total_invested:  number;
  current_value:   number;
  total_pnl:       number;
  total_pnl_pct:   number;
  day_pnl:         number;
  holdings_count:  number;
  updated_at:      string;
}

// ── Strategy ──────────────────────────────────────────────────
export type StrategyStatus = "draft" | "tested" | "active" | "paused" | "archived";

export interface Strategy {
  id:              string;
  name:            string;
  description:     string | null;
  strategy_type:   string;
  status:          StrategyStatus;
  version:         number;
  user_prompt:     string | null;
  python_code:     string | null;
  entry_logic:     string | null;
  exit_logic:      string | null;
  risk_rules:      string | null;
  indicators:      string[] | null;
  parameters:      Record<string, unknown> | null;
  symbols:         string[] | null;
  timeframe:       string;
  exchange:        string;
  stop_loss_pct:   number;
  take_profit_pct: number;
  backtest_results:Record<string, unknown> | null;
  is_public:       boolean;
  is_paper_active: boolean;
  is_live_active:  boolean;
  clone_count:     number;
  tags:            string[] | null;
  created_at:      string;
  updated_at:      string;
}

// ── Alerts ────────────────────────────────────────────────────
export type AlertCondition =
  | "above" | "below" | "percent_change"
  | "volume_spike" | "rsi_overbought" | "rsi_oversold"
  | "news_mention" | "sentiment_above" | "sentiment_below";
export type AlertStatus      = "active" | "triggered" | "paused" | "expired";
export type SentimentLabel   = "bullish" | "bearish" | "neutral";
export type NewsCategory     =
  | "bullish" | "bearish" | "neutral"
  | "earnings" | "macro" | "breaking" | "geopolitical" | "all";

export interface Alert {
  id:                      string;
  user_id:                 string;
  symbol:                  string;
  exchange:                string;
  name:                    string | null;
  condition:               AlertCondition;
  target_value:            number;
  current_value:           number | null;
  status:                  AlertStatus;
  is_repeating:            boolean;
  repeat_interval_minutes: number;
  channels:                string[];
  news_sources:            string[] | null;
  notes:                   string | null;
  trigger_count:           number;
  triggered_at:            string | null;
  last_checked_at:         string | null;
  expires_at:              string | null;
  created_at:              string;
  updated_at:              string;
}

export interface AlertListResponse {
  total:     number;
  active:    number;
  triggered: number;
  paused:    number;
  alerts:    Alert[];
}

export interface CreateAlertPayload {
  symbol:                   string;
  exchange?:                string;
  name?:                    string;
  condition:                AlertCondition;
  target_value:             number;
  is_repeating?:            boolean;
  repeat_interval_minutes?: number;
  channels?:                string[];
  news_sources?:            string[];
  notes?:                   string;
}

export interface Notification {
  id:                string;
  user_id:           string;
  alert_id:          string | null;
  title:             string;
  message:           string;
  symbol:            string | null;
  notification_type: string;
  data:              Record<string, unknown> | null;
  channel:           string;
  is_read:           boolean;
  read_at:           string | null;
  created_at:        string;
}

export interface NotificationListResponse {
  total:         number;
  unread:        number;
  notifications: Notification[];
}

export interface NewsArticle {
  id:              string;
  title:           string;
  summary:         string | null;
  url:             string;
  source:          string;
  published_at:    string;
  symbols:         string[];
  category:        NewsCategory;
  sentiment_score: number;
  confidence:      number;
  ai_summary:      string | null;
  image_url:       string | null;
}

export interface NewsFeedResponse {
  total:    number;
  page:     number;
  per_page: number;
  articles: NewsArticle[];
}

export interface SentimentData {
  symbol:      string;
  exchange:    string;
  score:       number;
  label:       SentimentLabel;
  confidence:  number;
  explanation: string | null;
  headlines:   string[] | null;
  news_count:  number;
  cached_at:   string | null;
  is_stale:    boolean;
}

export interface MarketSentimentSummary {
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  total:         number;
  avg_score:     number;
  top_bullish:   SentimentData | null;
  top_bearish:   SentimentData | null;
  updated_at:    string;
}

// ── News-driven stock screener ────────────────────────────────
export interface NewsScreenerRecommendation {
  symbol:         string;
  sector:         string;
  news_count:     number;
  headlines:      string[];
  avg_sentiment:  number;
  sources:        string[];
  screener_score: number | null;
  ltp:            number | null;
  change_pct:     number | null;
  rsi:            number | null;
  trend_up:       boolean | null;
  momentum_score: number | null;
  volume_ratio:   number | null;
}

export interface NewsScreenerSectorGroup {
  sector:       string;
  count:        number;
  avg_sentiment: number;
  total_news:   number;
  symbols:      string[];
  top_stock:    string | null;
}

export interface NewsScreenerResponse {
  symbols_analyzed: number;
  news_count:       number;
  sectors:          NewsScreenerSectorGroup[];
  recommendations:  NewsScreenerRecommendation[];
}

// Sector display configs
export const SECTOR_COLORS: Record<string, { border: string; text: string; bg: string; icon: string }> = {
  "Defense & Aerospace": { border: "border-green-500/30", text: "text-green-400", bg: "bg-green-500/10", icon: "🛡️" },
  "Energy":              { border: "border-orange-500/30", text: "text-orange-400", bg: "bg-orange-500/10", icon: "⚡" },
  "Banking & Finance":   { border: "border-blue-500/30", text: "text-blue-400", bg: "bg-blue-500/10", icon: "🏦" },
  "IT":                  { border: "border-purple-500/30", text: "text-purple-400", bg: "bg-purple-500/10", icon: "💻" },
  "Auto":                { border: "border-yellow-500/30", text: "text-yellow-400", bg: "bg-yellow-500/10", icon: "🚗" },
  "Pharma":              { border: "border-pink-500/30", text: "text-pink-400", bg: "bg-pink-500/10", icon: "💊" },
  "FMCG":                { border: "border-teal-500/30", text: "text-teal-400", bg: "bg-teal-500/10", icon: "🛒" },
  "Metals & Mining":     { border: "border-red-500/30", text: "text-red-400", bg: "bg-red-500/10", icon: "⛏️" },
  "Infrastructure":      { border: "border-cyan-500/30", text: "text-cyan-400", bg: "bg-cyan-500/10", icon: "🏗️" },
  "Telecom":             { border: "border-indigo-500/30", text: "text-indigo-400", bg: "bg-indigo-500/10", icon: "📡" },
  "Consumer":            { border: "border-rose-500/30", text: "text-rose-400", bg: "bg-rose-500/10", icon: "🛍️" },
  "Services":            { border: "border-gray-500/30", text: "text-gray-400", bg: "bg-gray-500/10", icon: "🔧" },
  "Other":               { border: "border-gray-500/30", text: "text-gray-400", bg: "bg-gray-500/10", icon: "📊" },
};

export const NEWS_SOURCES = [
  "Moneycontrol",
  "Economic Times",
  "Foreign Policy",
  "The Economist",
  "Geopolitical Monitor",
  "Finnhub",
] as const;

export type NewsSource = typeof NEWS_SOURCES[number];

export interface WSMessage {
  type:      string;
  data?:     unknown;
  message?:  string;
  timestamp: string;
}

// ── Display helpers ───────────────────────────────────────────
export const CONDITION_LABELS: Record<AlertCondition, string> = {
  above:          "Price Above",
  below:          "Price Below",
  percent_change: "% Change",
  volume_spike:   "Volume Spike",
  rsi_overbought: "RSI Overbought",
  rsi_oversold:   "RSI Oversold",
  news_mention:   "News Mention",
  sentiment_above:"Sentiment ≥",
  sentiment_below:"Sentiment ≤",
};

export const CONDITION_UNITS: Record<AlertCondition, string> = {
  above:          "₹",
  below:          "₹",
  percent_change: "%",
  volume_spike:   "×",
  rsi_overbought: "",
  rsi_oversold:   "",
  news_mention:   "",
  sentiment_above:"",
  sentiment_below:"",
};

export const SENTIMENT_COLORS: Record<SentimentLabel, string> = {
  bullish: "text-green-400 bg-green-400/10 border-green-500/30",
  bearish: "text-red-400   bg-red-400/10   border-red-500/30",
  neutral: "text-gray-400  bg-gray-400/10  border-gray-500/30",
};

export const CATEGORY_COLORS: Record<string, string> = {
  bullish:      "text-green-400  bg-green-400/10",
  bearish:      "text-red-400    bg-red-400/10",
  neutral:      "text-gray-400   bg-gray-800",
  earnings:     "text-purple-400 bg-purple-400/10",
  macro:        "text-blue-400   bg-blue-400/10",
  breaking:     "text-orange-400 bg-orange-400/10",
  geopolitical: "text-cyan-400   bg-cyan-400/10",
};
