import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { ModelProfile, ModelStatus } from "../types";

interface ModelSettingsPanelProps { status: ModelStatus | null; onClose: () => void; onRefresh: () => Promise<void>; }
type Provider = ModelProfile["provider"];
const emptyForm = { name: "新模型配置", provider: "deepseek" as Provider, model: "deepseek-chat", baseUrl: "", apiKeyEnv: "DEEPSEEK_API_KEY", secretValue: "", timeoutSeconds: 20, enabled: false };

export function ModelSettingsPanel({ status, onClose, onRefresh }: ModelSettingsPanelProps) {
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  const loadProfiles = async () => {
    setLoading(true);
    try { setProfiles(await apiClient.getModelProfiles()); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "读取模型配置失败"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void loadProfiles(); }, []);

  const selectProfile = (profile: ModelProfile) => {
    setEditingId(profile.id);
    setForm({ name: profile.name, provider: profile.provider, model: profile.model, baseUrl: profile.baseUrl, apiKeyEnv: profile.apiKeyEnv, secretValue: "", timeoutSeconds: profile.timeoutSeconds, enabled: profile.enabled });
    setResult("");
  };
  const updateProvider = (provider: Provider) => setForm((current) => ({
    ...current, provider,
    model: provider === "deepseek" ? "deepseek-chat" : provider === "openai" ? "gpt-4o-mini" : provider === "anthropic" ? "claude-3-5-sonnet-latest" : current.model,
    apiKeyEnv: provider === "deepseek" ? "DEEPSEEK_API_KEY" : provider === "openai" ? "OPENAI_API_KEY" : provider === "anthropic" ? "ANTHROPIC_API_KEY" : current.apiKeyEnv,
    baseUrl: provider === "openai_compatible" ? current.baseUrl : "",
  }));
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(""); setResult("");
    try {
      await apiClient.saveModelProfile(editingId, { name: form.name, provider: form.provider, model: form.model, base_url: form.baseUrl, api_key_env: form.apiKeyEnv, secret_value: form.secretValue, timeout_seconds: Number(form.timeoutSeconds), enabled: form.enabled });
      setForm((current) => ({ ...current, secretValue: "" })); await loadProfiles(); await onRefresh();
      setResult("配置已保存。当前运行服务仍使用启动时加载的配置，重启后生效。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存配置失败"); }
    finally { setSaving(false); }
  };
  const remove = async () => {
    if (!editingId) return;
    setSaving(true);
    try { await apiClient.deleteModelProfile(editingId); setEditingId(null); setForm(emptyForm); await loadProfiles(); setResult("配置已删除。"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "删除配置失败"); }
    finally { setSaving(false); }
  };
  const testConnection = async () => {
    setTesting(true); setResult(""); setError("");
    try { const response = await apiClient.testModel(); setResult(response.message); await onRefresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "连接测试失败"); }
    finally { setTesting(false); }
  };
  const input = (key: "name" | "model" | "baseUrl" | "apiKeyEnv" | "secretValue" | "timeoutSeconds", label: string, placeholder = "") => (
    <label className="model-field"><span>{label}</span><input type={key === "secretValue" ? "password" : key === "timeoutSeconds" ? "number" : "text"} value={form[key]} placeholder={placeholder} min={key === "timeoutSeconds" ? 1 : undefined} max={key === "timeoutSeconds" ? 120 : undefined} onChange={(event) => setForm((current) => ({ ...current, [key]: key === "timeoutSeconds" ? Number(event.target.value) : event.target.value }))} required={key !== "secretValue" && key !== "baseUrl"} /></label>
  );

  return <div className="create-backdrop" onMouseDown={onClose}>
    <section className="create-dialog model-dialog" onMouseDown={(event) => event.stopPropagation()}>
      <p className="eyebrow">AI DECISION ENGINE</p><h2>决策模型配置</h2>
      <p>模型配置保存在本地数据库。密钥仅写入、不回显；模型只复核候选信号，仓位和风控由系统确定。</p>
      <div className="model-status-grid">
        <span><small>当前提供方</small><strong>{status?.provider ?? "—"}</strong></span><span><small>当前模型</small><strong>{status?.model ?? "—"}</strong></span>
        <span><small>决策引擎</small><strong>{status?.decisionEnabled ? "已启用" : "未启用"}</strong></span><span><small>最低置信度</small><strong>{status ? `${Math.round(status.minimumConfidence * 100)}%` : "—"}</strong></span>
      </div>
      <div className="model-profile-heading"><strong>已保存配置</strong><button type="button" className="model-link" onClick={() => { setEditingId(null); setForm(emptyForm); setResult(""); }}>＋ 新建配置</button></div>
      {loading ? <p className="model-muted">正在读取配置…</p> : profiles.length === 0 ? <p className="model-muted">还没有已保存的配置。</p> : <div className="model-profile-list">{profiles.map((profile) => <button type="button" key={profile.id} className={`model-profile-row ${editingId === profile.id ? "selected" : ""}`} onClick={() => selectProfile(profile)}><span><strong>{profile.name}</strong><small>{profile.provider} · {profile.model}</small></span><span className="model-profile-tags">{profile.enabled && <i>默认</i>}{profile.secretConfigured && <i>密钥已存</i>}</span></button>)}</div>}
      <form className="model-form" onSubmit={save}>
        <div className="model-form-grid">{input("name", "配置名称", "例如：DeepSeek 主力")}
          <label className="model-field"><span>提供方</span><select value={form.provider} onChange={(event) => updateProvider(event.target.value as Provider)}><option value="deepseek">DeepSeek</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="openai_compatible">OpenAI 兼容接口</option></select></label>
          {input("model", "模型名称", "服务商提供的模型 ID")}{input("timeoutSeconds", "超时秒数")}
          {form.provider === "openai_compatible" && input("baseUrl", "接口基础地址", "https://example.com/v1")}
          {input("apiKeyEnv", "密钥环境变量名", "例如：MODEL_API_KEY")}{input("secretValue", editingId ? "替换 API 密钥（留空则保留）" : "API 密钥", "保存到本地数据库，不会返回浏览器")}
        </div>
        <label className="model-enabled"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))} />设为默认配置（服务重启后加载）</label>
        {error && <p className="model-form-error">{error}</p>}{result && <p className="model-test-result">{result}</p>}
        <p className="model-safety-note">连接失败、超时、格式错误或置信度不足时，系统会安全回退为 HOLD，不会创建订单。</p>
        <div className="create-actions">{editingId && <button type="button" className="model-delete" onClick={() => void remove()} disabled={saving}>删除配置</button>}<button type="button" className="cancel" onClick={onClose}>关闭</button><button type="button" className="cancel" onClick={() => void testConnection()} disabled={!status?.configured || testing}>{testing ? "正在验证…" : "测试当前连接"}</button><button type="submit" disabled={saving}>{saving ? "正在保存…" : "保存配置"}</button></div>
      </form>
    </section>
  </div>;
}
