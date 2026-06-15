"use client";
// Path: frontend/src/app/settings/page.tsx
import { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";
import {
  Shield, Bell, User, Key, ExternalLink,
  CheckCircle2, Loader2, AlertCircle, XCircle, Eye, EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Reusable status banner ────────────────────────────────────
function StatusBanner({ type, message }: { type: "success"|"error"; message: string }) {
  return (
    <div className={cn(
      "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium",
      type === "success"
        ? "bg-green-500/10 border border-green-500/20 text-green-400"
        : "bg-red-500/10 border border-red-500/20 text-red-400"
    )}>
      {type === "success"
        ? <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
        : <AlertCircle  className="h-4 w-4 flex-shrink-0" />}
      {message}
    </div>
  );
}

// ── Password field with show/hide ─────────────────────────────
function PasswordField({
  label, value, onChange, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || `Enter ${label}`}
          className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 pr-10 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-all"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

// ── Angel One section ─────────────────────────────────────────
function AngelOneSection() {
  const [apiKey,      setApiKey]      = useState("");
  const [clientId,    setClientId]    = useState("");
  const [password,    setPassword]    = useState("");
  const [totpSecret,  setTotpSecret]  = useState("");
  const [loading,     setLoading]     = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [status,      setStatus]      = useState<{ type: "success"|"error"; message: string } | null>(null);
  const [connected,   setConnected]   = useState(false);

  // Check broker status from backend on mount — persists across page navigations
  useEffect(() => {
    api.get("/brokers/status")
      .then((res) => {
        const brokers = res.data || [];
        if (brokers.length > 0 && brokers[0].is_connected) {
          setConnected(true);
          setClientId(brokers[0].client_id || "");
        }
      })
      .catch(() => {})
      .finally(() => setInitialLoading(false));
  }, []);

  const handleConnect = async () => {
    setStatus(null);
    if (!apiKey || !clientId || !password || !totpSecret) {
      setStatus({ type: "error", message: "All fields are required" });
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/brokers/angel-one/connect", {
        api_key:     apiKey,
        client_id:   clientId,
        password:    password,
        totp_secret: totpSecret,
      });
      setConnected(true);
      setStatus({ type: "success", message: res.data.message || "Connected to Angel One!" });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setStatus({
        type: "error",
        message: err.response?.data?.detail || "Connection failed. Check your credentials.",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await api.post("/brokers/disconnect/angel_one");
      setConnected(false);
      setStatus({ type: "success", message: "Disconnected from Angel One" });
    } catch {
      setStatus({ type: "error", message: "Failed to disconnect" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-xl bg-orange-500/15 flex items-center justify-center">
            <Key className="h-4 w-4 text-orange-400" />
          </div>
          <div>
            <h3 className="text-white font-bold">Angel One SmartAPI</h3>
            <p className="text-gray-500 text-xs">Connect your Angel One demat account</p>
          </div>
        </div>
        {connected && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-xl">
            <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400 text-xs font-semibold">Connected</span>
          </div>
        )}
      </div>

      {status && <div className="mb-4"><StatusBanner type={status.type} message={status.message} /></div>}

      <div className="space-y-3">
        <div>
          <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">API Key</label>
          <input
            type="text"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Your Angel One API Key"
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-all"
          />
        </div>
        <div>
          <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Client ID</label>
          <input
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="e.g. A123456"
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-all"
          />
        </div>
        <PasswordField label="Trading Password" value={password}   onChange={setPassword}   placeholder="Your trading PIN" />
        <PasswordField label="TOTP Secret"      value={totpSecret} onChange={setTotpSecret} placeholder="Base32 TOTP secret from Angel One" />

        <div className="flex items-center gap-2 pt-1">
          <a
            href="https://smartapi.angelone.in"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-blue-400 hover:underline"
          >
            Get API keys <ExternalLink className="h-3 w-3" />
          </a>
          <span className="text-gray-700 text-xs">·</span>
          <a
            href="https://smartapi.angelone.in/enable-totp"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-blue-400 hover:underline"
          >
            Enable TOTP <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <div className="flex gap-3 pt-2">
          {connected && (
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <XCircle className="h-4 w-4" /> Disconnect
            </button>
          )}
          <button
            onClick={handleConnect}
            disabled={loading}
            className="flex-1 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Connecting...</>
              : connected
              ? <><CheckCircle2 className="h-4 w-4" /> Reconnect</>
              : <><Key className="h-4 w-4" /> Connect Angel One</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Zerodha section ───────────────────────────────────────────
function ZerodhaSection() {
  const [apiKey,        setApiKey]        = useState("");
  const [apiSecret,     setApiSecret]     = useState("");
  const [requestToken,  setRequestToken]  = useState("");
  const [loading,       setLoading]       = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [status,        setStatus]        = useState<{ type: "success"|"error"; message: string; loginUrl?: string } | null>(null);
  const [connected,     setConnected]     = useState(false);
  const [loginId,       setLoginId]       = useState("");

  // Check Zerodha status from backend on mount
  useEffect(() => {
    api.get("/brokers/status")
      .then((res) => {
        const brokers = (res.data || []) as Array<{ broker: string; is_connected: boolean; client_id?: string }>;
        const zd = brokers.find((b) => b.broker === "zerodha");
        if (zd?.is_connected) {
          setConnected(true);
          setLoginId(zd.client_id || "");
        }
      })
      .catch(() => {})
      .finally(() => setInitialLoading(false));
  }, []);

  const handleConnect = async () => {
    setStatus(null);
    if (!apiKey || !apiSecret) {
      setStatus({ type: "error", message: "Both API Key and Secret are required" });
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/brokers/zerodha/connect", {
        api_key:    apiKey,
        api_secret: apiSecret,
      });
      setStatus({
        type: "success",
        message: res.data.message,
        loginUrl: res.data.login_url,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setStatus({
        type: "error",
        message: err.response?.data?.detail || "Failed to save credentials",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteOAuth = async () => {
    setStatus(null);
    if (!requestToken.trim()) {
      setStatus({ type: "error", message: "Please paste the request_token from the callback URL" });
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/brokers/zerodha/callback", {
        request_token: requestToken.trim(),
        api_key:       apiKey,
        api_secret:    apiSecret,
      });
      setConnected(true);
      setLoginId(res.data.login_id || "");
      setStatus({ type: "success", message: res.data.message || "Connected to Zerodha!" });
      setRequestToken("");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setStatus({
        type: "error",
        message: err.response?.data?.detail || "OAuth completion failed. Check your request_token.",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await api.post("/brokers/disconnect/zerodha");
      setConnected(false);
      setLoginId("");
      setStatus({ type: "success", message: "Disconnected from Zerodha" });
    } catch {
      setStatus({ type: "error", message: "Failed to disconnect" });
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-5">
          <div className="h-8 w-8 rounded-xl bg-green-500/15 flex items-center justify-center">
            <Loader2 className="h-4 w-4 animate-spin text-green-400" />
          </div>
          <div>
            <h3 className="text-white font-bold">Zerodha Kite Connect</h3>
            <p className="text-gray-500 text-xs">Checking connection...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-xl bg-green-500/15 flex items-center justify-center">
            <Key className="h-4 w-4 text-green-400" />
          </div>
          <div>
            <h3 className="text-white font-bold">Zerodha Kite Connect</h3>
            <p className="text-gray-500 text-xs">Connect via OAuth — no password stored</p>
          </div>
        </div>
        {connected && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-xl">
            <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400 text-xs font-semibold">Connected</span>
          </div>
        )}
      </div>

      {status && <div className="mb-4"><StatusBanner type={status.type} message={status.message} /></div>}

      <div className="space-y-3">
        {/* Connected info banner */}
        {connected && loginId && (
          <div className="flex items-center gap-2.5 bg-green-500/10 border border-green-500/20 rounded-xl px-4 py-2.5">
            <User className="h-4 w-4 text-green-400 flex-shrink-0" />
            <div>
              <p className="text-green-400 text-xs font-semibold">Connected as</p>
              <p className="text-white font-bold text-sm">{loginId}</p>
            </div>
          </div>
        )}

        <div>
          <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">API Key</label>
          <input
            type="text"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Your Kite API Key"
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-green-500 transition-all"
          />
        </div>
        <PasswordField label="API Secret" value={apiSecret} onChange={setApiSecret} placeholder="Your Kite API Secret" />

        <a
          href="https://developers.kite.trade"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-xs text-blue-400 hover:underline pt-1"
        >
          Create a Kite Connect app <ExternalLink className="h-3 w-3" />
        </a>

        {/* Step 1: Setup / get OAuth URL */}
        {!status?.loginUrl && !connected && (
          <button
            onClick={handleConnect}
            disabled={loading}
            className="w-full py-2.5 bg-green-700 hover:bg-green-600 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving...</>
              : <><Key className="h-4 w-4" /> Setup Zerodha</>
            }
          </button>
        )}

        {/* Step 2: OAuth login link + request token input */}
        {status?.loginUrl && !connected && (
          <div className="space-y-3 border-t border-gray-800 pt-3">
            <a
              href={status.loginUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all"
            >
              <ExternalLink className="h-4 w-4" />
              Complete Login on Zerodha
            </a>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-800" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-gray-900 px-3 text-gray-500">After login, paste the request_token below</span>
              </div>
            </div>

            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">
                Request Token
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={requestToken}
                  onChange={(e) => setRequestToken(e.target.value)}
                  placeholder="e.g. A1b2C3d4E5f6G7h8I9j0K..."
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 pr-32 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-green-500 transition-all"
                />
                <button
                  onClick={handleCompleteOAuth}
                  disabled={loading || !requestToken.trim()}
                  className="absolute right-1 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-xs font-semibold transition-all disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    "Complete"
                  )}
                </button>
              </div>
              <p className="text-gray-600 text-xs mt-1.5">
                After logging in, copy the <code className="text-gray-500 bg-gray-800 px-1 py-0.5 rounded text-[11px]">request_token</code> parameter from the callback URL and paste it above.
              </p>
            </div>
          </div>
        )}

        {/* Action buttons: disconnect or restart flow */}
        <div className="flex gap-3">
          {connected && (
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <XCircle className="h-4 w-4" /> Disconnect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main settings page ────────────────────────────────────────
export default function SettingsPage() {
  const { user } = useAuthStore();
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChat,  setTelegramChat]  = useState("");
  const [alertStatus,   setAlertStatus]   = useState<{ type: "success"|"error"; message: string } | null>(null);
  const [savingAlerts,  setSavingAlerts]  = useState(false);

  // Load existing Telegram settings from user profile on mount
  useEffect(() => {
    api.get("/users/me")
      .then((res) => {
        const u = res.data;
        if (u.telegram_bot_token) setTelegramToken(u.telegram_bot_token);
        if (u.telegram_chat_id)   setTelegramChat(u.telegram_chat_id);
      })
      .catch(() => {});
  }, []);

  const saveAlertSettings = async () => {
    setAlertStatus(null);
    setSavingAlerts(true);
    try {
      await api.put("/users/me", {
        telegram_bot_token: telegramToken,
        telegram_chat_id: telegramChat,
      });
      setAlertStatus({ type: "success", message: "Telegram settings saved! Messages will be sent to your chat." });
      setTimeout(() => setAlertStatus(null), 4000);
    } catch {
      setAlertStatus({ type: "error", message: "Failed to save Telegram settings. Please try again." });
    } finally {
      setSavingAlerts(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-3xl space-y-6">
        <div>
          <h2 className="text-2xl font-black text-white">Settings</h2>
          <p className="text-gray-400 text-sm mt-0.5">Manage your account, brokers and preferences</p>
        </div>

        {/* Security notice */}
        <div className="flex gap-3 bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
          <Shield className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-blue-400 font-semibold text-sm">Your credentials are secure</p>
            <p className="text-blue-300/70 text-xs mt-0.5">
              API keys are stored encrypted in your local database. They are never sent to any third-party service.
            </p>
          </div>
        </div>

        {/* Profile */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-5">
            <div className="h-8 w-8 rounded-xl bg-blue-500/15 flex items-center justify-center">
              <User className="h-4 w-4 text-blue-400" />
            </div>
            <h3 className="text-white font-bold">Profile</h3>
          </div>
          <div className="space-y-2">
            {[
              ["Email",    user?.email    ?? ""],
              ["Username", user?.username ?? ""],
              ["Role",     user?.role     ?? "trader"],
            ].map(([l, v]) => (
              <div key={String(l)} className="flex items-center justify-between p-3 bg-gray-800 rounded-xl">
                <span className="text-gray-400 text-sm">{l}</span>
                <span className="text-white text-sm font-medium">{v}</span>
              </div>
            ))}
            <div className="flex items-center justify-between p-3 bg-gray-800 rounded-xl">
              <span className="text-gray-400 text-sm">Verified</span>
              {user?.is_verified
                ? <span className="flex items-center gap-1 text-green-400 text-sm"><CheckCircle2 className="h-3.5 w-3.5" /> Yes</span>
                : <span className="text-yellow-400 text-sm">Pending email verification</span>}
            </div>
          </div>
        </div>

        {/* Broker connections */}
        <AngelOneSection />
        <ZerodhaSection />

        {/* Alert preferences */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-5">
            <div className="h-8 w-8 rounded-xl bg-yellow-500/15 flex items-center justify-center">
              <Bell className="h-4 w-4 text-yellow-400" />
            </div>
            <h3 className="text-white font-bold">Alert Preferences</h3>
          </div>

          {alertStatus && <div className="mb-4"><StatusBanner type={alertStatus.type} message={alertStatus.message} /></div>}

          <div className="space-y-3">
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">
                Telegram Bot Token
              </label>
              <input
                type="text"
                value={telegramToken}
                onChange={(e) => setTelegramToken(e.target.value)}
                placeholder="Token from @BotFather"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-yellow-500 transition-all"
              />
            </div>
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">
                Telegram Chat ID
              </label>
              <input
                type="text"
                value={telegramChat}
                onChange={(e) => setTelegramChat(e.target.value)}
                placeholder="Your chat ID from @userinfobot"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-yellow-500 transition-all"
              />
            </div>
            <button
              onClick={saveAlertSettings}
              className="w-full py-2.5 bg-yellow-600 hover:bg-yellow-500 text-white rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2"
            >
              <Bell className="h-4 w-4" /> Save Alert Settings
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
