import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import { BrokerSettingsPanel } from "./BrokerSettingsPanel";
import type { ModelProfile, ModelStatus } from "../types";

interface ModelSettingsPanelProps {
  status: ModelStatus | null;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}

type Provider = ModelProfile["provider"];
type ProfileForm = {
  name: string;
  provider: Provider;
  model: string;
  baseUrl: string;
  apiKeyEnv: string;
  secretValue: string;
  timeoutSeconds: number;
  enabled: boolean;
};

const emptyForm: ProfileForm = {
  name: "",
  provider: "deepseek",
  model: "deepseek-chat",
  baseUrl: "",
  apiKeyEnv: "DEEPSEEK_API_KEY",
  secretValue: "",
  timeoutSeconds: 20,
  enabled: false,
};

const providerLabels: Record<Provider, string> = {
  openai: "OpenAI",
  deepseek: "DeepSeek",
  anthropic: "Anthropic",
  openai_compatible: "OpenAI 兼容接口",
};

export function ModelSettingsPanel({ status, onClose, onRefresh }: ModelSettingsPanelProps) {
  const [activeTab, setActiveTab] = useState<"model" | "broker">("model");
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [form, setForm] = useState<ProfileForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const loadProfiles = async () => {
    setLoading(true);
    try {
      setProfiles(await apiClient.getModelProfiles());
      setLoadError("");
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "读取模型配置失败，请重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadProfiles(); }, []);

  const startNew = () => {
    setEditingId(null);
    setForm(emptyForm);
    setError("");
    setResult("");
  };

  const selectProfile = (profile: ModelProfile) => {
    setEditingId(profile.id);
    setForm({
      name: profile.name,
      provider: profile.provider,
      model: profile.model,
      baseUrl: profile.baseUrl,
      apiKeyEnv: profile.apiKeyEnv,
      secretValue: "",
      timeoutSeconds: profile.timeoutSeconds,
      enabled: profile.enabled,
    });
    setError("");
    setResult("");
  };

  const updateProvider = (provider: Provider) => setForm((current) => ({
    ...current,
    provider,
    model: provider === "deepseek" ? "deepseek-chat" : provider === "openai" ? "gpt-4o-mini" : provider === "anthropic" ? "claude-3-5-sonnet-latest" : current.model,
    apiKeyEnv: provider === "deepseek" ? "DEEPSEEK_API_KEY" : provider === "openai" ? "OPENAI_API_KEY" : provider === "anthropic" ? "ANTHROPIC_API_KEY" : current.apiKeyEnv,
    baseUrl: provider === "openai_compatible" ? current.baseUrl : "",
  }));

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setResult("");
    try {
      await apiClient.saveModelProfile(editingId, {
        name: form.name,
        provider: form.provider,
        model: form.model,
        base_url: form.baseUrl,
        api_key_env: form.apiKeyEnv,
        secret_value: form.secretValue,
        timeout_seconds: Number(form.timeoutSeconds),
        enabled: form.enabled,
      });
      setForm((current) => ({ ...current, secretValue: "" }));
      await loadProfiles();
      await onRefresh();
      setResult("配置已保存。当前服务会在重启后加载默认配置。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请检查配置后重试。");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!editingId) return;
    setSaving(true);
    setError("");
    setResult("");
    try {
      await apiClient.deleteModelProfile(editingId);
      setEditingId(null);
      setForm(emptyForm);
      await loadProfiles();
      setResult("配置已删除。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败，请重试。");
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setResult("");
    setError("");
    try {
      const response = await apiClient.testModel();
      setResult(response.message);
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "连接测试失败，请检查后端服务和模型配置。");
    } finally {
      setTesting(false);
    }
  };

  const input = (
    key: "name" | "model" | "baseUrl" | "apiKeyEnv" | "secretValue" | "timeoutSeconds",
    label: string,
    placeholder = "",
    help?: string,
  ) => (
    <label className={`model-field ${key === "secretValue" ? "model-field-wide" : ""}`}>
      <span className="model-field-label">{label}</span>
      <input
        type={key === "secretValue" ? "password" : key === "timeoutSeconds" ? "number" : "text"}
        value={form[key]}
        placeholder={placeholder}
        min={key === "timeoutSeconds" ? 1 : undefined}
        max={key === "timeoutSeconds" ? 120 : undefined}
        onChange={(event) => setForm((current) => ({
          ...current,
          [key]: key === "timeoutSeconds" ? Number(event.target.value) : event.target.value,
        }))}
        required={key === "name" || key === "model" || key === "apiKeyEnv" || (key === "secretValue" && !editingId)}
        autoComplete={key === "secretValue" ? "new-password" : "off"}
      />
      {help && <small>{help}</small>}
    </label>
  );

  return (
    <div className="create-backdrop model-backdrop" onMouseDown={onClose}>
      <section
        className="create-dialog model-dialog"
        aria-labelledby="model-settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="model-dialog-heading">
          <div>
            <p className="eyebrow">CONNECTION SETTINGS</p>
            <h2 id="model-settings-title">连接配置</h2>
            <p>管理决策模型和券商账户的连接信息。</p>
          </div>
          <button type="button" className="model-close" aria-label="关闭" onClick={onClose}>×</button>
        </header>

        <nav className="model-settings-tabs" role="tablist" aria-label="连接配置类型">
          <button type="button" role="tab" aria-selected={activeTab === "model"} className={activeTab === "model" ? "active" : ""} onClick={() => setActiveTab("model")}>
            <span>✦</span>决策模型
          </button>
          <button type="button" role="tab" aria-selected={activeTab === "broker"} className={activeTab === "broker" ? "active" : ""} onClick={() => setActiveTab("broker")}>
            <span>↗</span>交易券商
          </button>
        </nav>

        {activeTab === "model" ? <>
        <section className="model-runtime" aria-label="当前运行状态">
          <div className="model-runtime-heading">
            <span className={`model-runtime-dot ${status?.configured ? "online" : "offline"}`} />
            <strong>当前运行配置</strong>
            <span>{status?.configured ? "已连接凭证" : "未加载凭证"}</span>
          </div>
          <div className="model-runtime-grid">
            <div><small>提供方</small><strong>{status?.provider ?? "—"}</strong></div>
            <div><small>模型</small><strong>{status?.model ?? "—"}</strong></div>
            <div><small>决策引擎</small><strong>{status?.decisionEnabled ? "已启用" : "未启用"}</strong></div>
            <div><small>最低置信度</small><strong>{status ? `${Math.round(status.minimumConfidence * 100)}%` : "—"}</strong></div>
          </div>
        </section>

        <div className="model-settings-layout">
          <aside className="model-profiles-pane">
            <div className="model-pane-heading">
              <div><h3>已保存配置</h3><span>{profiles.length} 个配置</span></div>
              <button type="button" className="model-add" onClick={startNew}>＋ 新建</button>
            </div>
            {loadError && (
              <div className="model-load-error" role="alert">
                <strong>配置列表加载失败</strong>
                <p>{loadError}</p>
                <button type="button" onClick={() => void loadProfiles()}>重新加载</button>
              </div>
            )}
            {loading ? (
              <div className="model-empty"><span className="model-spinner" />正在读取配置…</div>
            ) : profiles.length === 0 ? (
              <div className="model-empty"><span className="model-empty-icon">＋</span><strong>还没有模型配置</strong><small>创建一个配置以便保存连接信息。</small></div>
            ) : (
              <div className="model-profile-list">
                {profiles.map((profile) => (
                  <button
                    type="button"
                    key={profile.id}
                    className={`model-profile-row ${editingId === profile.id ? "selected" : ""}`}
                    onClick={() => selectProfile(profile)}
                  >
                    <span className="model-profile-icon">{providerLabels[profile.provider].slice(0, 1)}</span>
                    <span className="model-profile-copy"><strong>{profile.name}</strong><small>{providerLabels[profile.provider]} · {profile.model}</small></span>
                    <span className="model-profile-tags">{profile.enabled && <i>默认</i>}</span>
                  </button>
                ))}
              </div>
            )}
            <div className="model-runtime-note"><strong>生效方式</strong><span>保存默认配置后，重启后端服务以加载。</span></div>
          </aside>

          <form className="model-editor-pane" onSubmit={save}>
            <div className="model-editor-heading">
              <div><h3>{editingId ? "编辑配置" : "新建配置"}</h3><p>填写模型服务的连接参数。</p></div>
              {editingId && <span className="model-secret-badge">{profiles.find((profile) => profile.id === editingId)?.secretConfigured ? "密钥已保存" : "未设置密钥"}</span>}
            </div>
            <div className="model-form-grid">
              {input("name", "配置名称", "例如：DeepSeek 主力")}
              <label className="model-field">
                <span className="model-field-label">模型提供方</span>
                <select value={form.provider} onChange={(event) => updateProvider(event.target.value as Provider)}>
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="openai_compatible">OpenAI 兼容接口</option>
                </select>
              </label>
              {input("model", "模型名称", "填写服务商提供的模型 ID")}
              {input("timeoutSeconds", "请求超时", "", "秒，范围 1–120")}
              {form.provider === "openai_compatible" && input("baseUrl", "API 基础地址", "https://example.com/v1")}
              {input("apiKeyEnv", "密钥环境变量名", "例如：DEEPSEEK_API_KEY")}
              {input("secretValue", editingId ? "替换 API 密钥" : "API 密钥", editingId ? "留空表示继续使用已保存的密钥" : "输入服务商提供的 API 密钥", "密钥只写入，不会回显。")}
            </div>
            <label className="model-default-option">
              <input type="checkbox" checked={form.enabled} onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))} />
              <span><strong>设为默认模型</strong><small>应用启动时使用这组配置。</small></span>
            </label>

            {error && <div className="model-feedback error" role="alert">{error}</div>}
            {result && <div className="model-feedback success" role="status">{result}</div>}

            <div className="model-editor-footer">
              {editingId ? <button type="button" className="model-delete" onClick={() => void remove()} disabled={saving}>删除配置</button> : <span className="model-safety-hint">模型只复核信号，风控仍由系统执行。</span>}
              <div className="model-editor-actions">
                <button type="button" className="model-secondary" onClick={() => void testConnection()} disabled={!status?.configured || testing}>{testing ? "正在测试…" : "测试当前连接"}</button>
                <button type="submit" className="model-primary" disabled={saving}>{saving ? "正在保存…" : "保存配置"}</button>
              </div>
            </div>
          </form>
        </div>
        </> : <BrokerSettingsPanel />}
      </section>
    </div>
  );
}
