"use client";
// Path: frontend/src/app/ai-models/page.tsx
// Phase 6 — AI Model Management. Users add API keys for each provider, test, activate, and reorder fallback chain.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Brain, Plug, CheckCircle2, AlertTriangle, Save, Play, Trash2, Power, ArrowUp, ArrowDown, Loader2 } from "lucide-react";

interface ProviderInfo  { provider: string; default_model: string; category: "cloud" | "local" }
interface AIConfig {
  id: string; provider: string; label: string | null;
  api_key_preview: string | null; base_url: string | null;
  model: string; temperature: number; max_tokens: number;
  system_prompt: string | null; is_active: boolean; fallback_order: number;
  last_test_status: string | null; last_test_message: string | null; last_tested_at: string | null;
}

const PROVIDER_META: Record<string, { label: string; color: string }> = {
  openai:     { label: "OpenAI",      color: "from-emerald-500 to-emerald-600" },
  anthropic:  { label: "Anthropic",   color: "from-amber-500 to-orange-500" },
  gemini:     { label: "Google Gemini", color: "from-sky-500 to-indigo-500" },
  openrouter: { label: "OpenRouter",  color: "from-purple-500 to-pink-500" },
  groq:       { label: "Groq",        color: "from-red-500 to-pink-600" },
  deepseek:   { label: "DeepSeek",    color: "from-blue-500 to-cyan-500" },
  mistral:    { label: "Mistral",     color: "from-orange-500 to-yellow-500" },
  perplexity: { label: "Perplexity",  color: "from-teal-500 to-cyan-500" },
  ollama:     { label: "Ollama (Local)", color: "from-gray-500 to-gray-700" },
};

export default function AIModelsPage() {
  const qc = useQueryClient();
  const { data: providers = [] } = useQuery<ProviderInfo[]>({
    queryKey: ["ai-providers"], queryFn: () => api.get("/ai-models/providers").then((r) => r.data),
  });
  const { data: configs = [] } = useQuery<AIConfig[]>({
    queryKey: ["ai-configs"], queryFn: () => api.get("/ai-models").then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<any>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; message: string; latency_ms?: number } | null>(null);

  const saveMut = useMutation({
    mutationFn: (body: any) => api.post("/ai-models", body).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ai-configs"] }); setEditing(null); setForm({}); },
  });
  const delMut = useMutation({
    mutationFn: (id: string) => api.delete(`/ai-models/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-configs"] }),
  });
  const activateMut = useMutation({
    mutationFn: (id: string) => api.post(`/ai-models/${id}/activate`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-configs"] }),
  });
  const reorderMut = useMutation({
    mutationFn: (order: string[]) => api.post("/ai-models/reorder", { order }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-configs"] }),
  });

  const openEdit = (provider: string) => {
    const existing = configs.find((c) => c.provider === provider);
    setEditing(provider);
    setForm({
      provider,
      label:    existing?.label ?? PROVIDER_META[provider]?.label,
      api_key:  "",
      base_url: existing?.base_url ?? (provider === "ollama" ? "http://localhost:11434" : ""),
      model:    existing?.model ?? providers.find((p) => p.provider === provider)?.default_model ?? "",
      temperature:  existing?.temperature ?? 0.3,
      max_tokens:   existing?.max_tokens ?? 2048,
      system_prompt: existing?.system_prompt ?? "",
    });
  };

  const runTest = async (id: string) => {
    setTesting(id); setTestResult(null);
    try {
      const r = await api.post(`/ai-models/${id}/test`);
      setTestResult({ id, ok: r.data.ok, message: r.data.message, latency_ms: r.data.latency_ms });
    } catch (e: any) {
      setTestResult({ id, ok: false, message: e?.response?.data?.detail ?? String(e) });
    } finally { setTesting(null); qc.invalidateQueries({ queryKey: ["ai-configs"] }); }
  };

  const moveFallback = (idx: number, dir: -1 | 1) => {
    const ordered = [...configs].sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.fallback_order - b.fallback_order);
    const j = idx + dir;
    if (j < 0 || j >= ordered.length) return;
    [ordered[idx], ordered[j]] = [ordered[j], ordered[idx]];
    reorderMut.mutate(ordered.map((c) => c.id));
  };

  const ordered = [...configs].sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.fallback_order - b.fallback_order);

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="ai-models-root">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-sky-500/10 border border-sky-500/30 rounded-full text-sky-300 text-[11px] font-bold tracking-widest uppercase mb-2">
            <Brain className="h-3 w-3" /> AI Model Management
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">AI Models</h1>
          <p className="text-gray-500 text-sm mt-1">Bring your own keys for any provider, plus run local models via Ollama. Set a primary + fallback chain.</p>
        </div>

        {/* Provider grid */}
        <div>
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-3">Available providers</p>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
            {providers.map((p) => {
              const cfg = configs.find((c) => c.provider === p.provider);
              const meta = PROVIDER_META[p.provider] ?? { label: p.provider, color: "from-gray-500 to-gray-700" };
              return (
                <button key={p.provider} onClick={() => openEdit(p.provider)} data-testid={`provider-card-${p.provider}`}
                  className="text-left bg-gray-900/60 border border-gray-800 hover:border-amber-500/30 rounded-2xl p-4 transition-all group">
                  <div className={cn("h-9 w-9 rounded-xl bg-gradient-to-br mb-3 flex items-center justify-center text-white font-black", meta.color)}>
                    {meta.label[0]}
                  </div>
                  <p className="text-white font-bold text-sm">{meta.label}</p>
                  <p className="text-gray-500 text-xs mt-0.5">{p.default_model}</p>
                  <p className="text-[10px] mt-2 font-bold uppercase tracking-wider">
                    {cfg
                      ? <span className={cfg.is_active ? "text-emerald-400" : "text-amber-300"}>{cfg.is_active ? "Active" : "Configured"}</span>
                      : <span className="text-gray-600">Not configured</span>}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Configured models — primary + fallback chain */}
        <div>
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-3">Primary &amp; fallback chain</p>
          <div className="bg-gray-900/60 border border-gray-800 rounded-2xl divide-y divide-gray-800" data-testid="ai-chain-list">
            {ordered.length === 0 && (
              <div className="px-5 py-10 text-center text-gray-500 text-sm">No models configured yet. Pick a provider above to add one.</div>
            )}
            {ordered.map((c, idx) => {
              const meta = PROVIDER_META[c.provider] ?? { label: c.provider, color: "from-gray-500 to-gray-700" };
              const isPrimary = idx === 0;
              return (
                <div key={c.id} className="flex items-center gap-4 p-4" data-testid={`ai-config-row-${c.provider}`}>
                  <div className="w-7 text-center font-mono text-xs text-gray-500">{idx === 0 ? "★" : `#${idx + 1}`}</div>
                  <div className={cn("h-10 w-10 rounded-xl bg-gradient-to-br flex items-center justify-center text-white font-black", meta.color)}>{meta.label[0]}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-white font-bold text-sm">{meta.label}</p>
                      {isPrimary && <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-amber-500/15 text-amber-300 border border-amber-500/30 rounded">Primary</span>}
                      {c.last_test_status === "ok" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
                      {c.last_test_status === "error" && <AlertTriangle className="h-3.5 w-3.5 text-red-400" />}
                    </div>
                    <p className="text-gray-500 text-xs mt-0.5">{c.model} · key {c.api_key_preview ?? "<universal>"}</p>
                  </div>
                  <button onClick={() => moveFallback(idx, -1)} disabled={idx === 0} data-testid={`ai-move-up-${c.provider}`} className="text-gray-500 hover:text-white p-1.5 disabled:opacity-30"><ArrowUp className="h-4 w-4" /></button>
                  <button onClick={() => moveFallback(idx, 1)} disabled={idx === ordered.length - 1} data-testid={`ai-move-down-${c.provider}`} className="text-gray-500 hover:text-white p-1.5 disabled:opacity-30"><ArrowDown className="h-4 w-4" /></button>
                  {!isPrimary && <button onClick={() => activateMut.mutate(c.id)} data-testid={`ai-activate-${c.provider}`} className="px-2.5 py-1.5 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/30 text-xs font-bold hover:bg-amber-500/25"><Power className="h-3.5 w-3.5 inline mr-1" />Make Primary</button>}
                  <button onClick={() => runTest(c.id)} disabled={testing === c.id} data-testid={`ai-test-${c.provider}`} className="px-2.5 py-1.5 rounded-lg bg-gray-800 text-gray-200 border border-gray-700 text-xs font-bold hover:bg-gray-700 disabled:opacity-50">
                    {testing === c.id ? <Loader2 className="h-3.5 w-3.5 inline animate-spin" /> : <><Play className="h-3.5 w-3.5 inline mr-1" />Test</>}
                  </button>
                  <button onClick={() => openEdit(c.provider)} data-testid={`ai-edit-${c.provider}`} className="px-2.5 py-1.5 rounded-lg bg-gray-800 text-gray-200 border border-gray-700 text-xs font-bold hover:bg-gray-700">Edit</button>
                  <button onClick={() => delMut.mutate(c.id)} data-testid={`ai-delete-${c.provider}`} className="text-gray-500 hover:text-red-400 p-1.5"><Trash2 className="h-4 w-4" /></button>
                </div>
              );
            })}
          </div>
          {testResult && (
            <div className={cn("mt-3 px-4 py-3 rounded-xl border text-sm", testResult.ok ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" : "bg-red-500/10 border-red-500/30 text-red-300")}
                 data-testid="ai-test-result">
              {testResult.ok ? <CheckCircle2 className="h-4 w-4 inline mr-2" /> : <AlertTriangle className="h-4 w-4 inline mr-2" />}
              {testResult.message}{testResult.latency_ms != null && ` · ${testResult.latency_ms}ms`}
            </div>
          )}
        </div>

        {/* Editor modal */}
        {editing && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setEditing(null)} data-testid="ai-editor-overlay">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()} data-testid="ai-editor-modal">
              <div className="flex items-center gap-3 mb-5">
                <div className={cn("h-10 w-10 rounded-xl bg-gradient-to-br flex items-center justify-center text-white font-black", PROVIDER_META[editing].color)}>
                  {PROVIDER_META[editing].label[0]}
                </div>
                <div>
                  <p className="text-white font-bold">{PROVIDER_META[editing].label}</p>
                  <p className="text-gray-500 text-xs">{editing === "ollama" ? "Local model — runs on your machine" : "Cloud provider"}</p>
                </div>
              </div>

              <div className="space-y-3">
                <Field label="Model">
                  <input data-testid="ai-form-model" value={form.model ?? ""} onChange={(e) => setForm({ ...form, model: e.target.value })} className={inputCls} placeholder={providers.find((p) => p.provider === editing)?.default_model} />
                </Field>
                {editing !== "ollama" && (
                  <Field label="API Key" hint={["openai", "anthropic", "gemini"].includes(editing) ? "Optional — leave blank to use Emergent Universal key" : "Required"}>
                    <input data-testid="ai-form-key" type="password" autoComplete="off" value={form.api_key ?? ""} onChange={(e) => setForm({ ...form, api_key: e.target.value })} className={inputCls} placeholder="sk-…" />
                  </Field>
                )}
                {(editing === "ollama" || editing === "openrouter") && (
                  <Field label="Base URL">
                    <input data-testid="ai-form-base-url" value={form.base_url ?? ""} onChange={(e) => setForm({ ...form, base_url: e.target.value })} className={inputCls} placeholder={editing === "ollama" ? "http://localhost:11434" : "https://openrouter.ai/api/v1"} />
                  </Field>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Temperature">
                    <input data-testid="ai-form-temperature" type="number" step="0.05" min="0" max="2" value={form.temperature ?? 0.3} onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })} className={inputCls} />
                  </Field>
                  <Field label="Max Tokens">
                    <input data-testid="ai-form-max-tokens" type="number" min="64" max="32000" value={form.max_tokens ?? 2048} onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) })} className={inputCls} />
                  </Field>
                </div>
                <Field label="System Prompt">
                  <textarea data-testid="ai-form-system-prompt" rows={3} value={form.system_prompt ?? ""} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} className={inputCls} placeholder="You are a helpful trading analyst…" />
                </Field>
              </div>

              <div className="flex items-center gap-2 mt-5 justify-end">
                <button onClick={() => { setEditing(null); setForm({}); }} className="px-4 py-2 text-gray-400 hover:text-white text-sm" data-testid="ai-editor-cancel">Cancel</button>
                <button onClick={() => saveMut.mutate(form)} disabled={saveMut.isPending} data-testid="ai-editor-save"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 rounded-xl text-sm font-bold">
                  {saveMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

const inputCls = "w-full px-3 py-2 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white placeholder-gray-600 outline-none";

function Field({ label, hint, children }: { label: string; hint?: string; children: any }) {
  return (
    <div>
      <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">{label}{hint && <span className="ml-2 text-gray-600 font-normal normal-case">· {hint}</span>}</label>
      {children}
    </div>
  );
}
