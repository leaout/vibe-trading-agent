import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { BrokerConfig } from "../types";

const emptyConfig: BrokerConfig = {
  provider: "eastmoney",
  configured: false,
  accountHint: "",
  accountConfigured: false,
  passwordConfigured: false,
  sessionFile: "data/eastmoney_trader.session",
  updatedAt: null,
};

export function BrokerSettingsPanel() {
  const [config, setConfig] = useState<BrokerConfig>(emptyConfig);
  const [accountNo, setAccountNo] = useState("");
  const [password, setPassword] = useState("");
  const [sessionFile, setSessionFile] = useState(emptyConfig.sessionFile);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const loaded = await apiClient.getBrokerConfig();
      setConfig(loaded);
      setSessionFile(loaded.sessionFile);
      setLoadError("");
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "读取券商配置失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const saved = await apiClient.saveBrokerConfig({
        account_no: accountNo,
        password,
        session_file: sessionFile,
      });
      setConfig(saved);
      setAccountNo("");
      setPassword("");
      setMessage("东方财富凭证已加密保存。当前 V2 服务尚未使用此配置建立券商连接。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存券商配置失败，请检查后重试。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="broker-settings-content">
      <section className="broker-current-card">
        <div className="broker-current-icon">东</div>
        <div className="broker-current-copy">
          <strong>东方财富</strong>
          <span>A 股交易账户配置</span>
        </div>
        <span className={`broker-config-state ${config.configured ? "saved" : "empty"}`}>
          <i />{config.configured ? "凭证已保存" : "尚未配置"}
        </span>
      </section>

      <div className="broker-safety-notice" role="note">
        <span className="broker-notice-icon">!</span>
        <p><strong>配置不代表已连接</strong>当前 V2 尚未接入东方财富交易适配器。保存只会加密保管凭证，不会登录账户、读取资金或发送订单。</p>
      </div>

      {loadError && (
        <div className="model-load-error broker-load-error" role="alert">
          <strong>券商配置读取失败</strong>
          <p>{loadError}</p>
          <button type="button" onClick={() => void load()}>重新加载</button>
        </div>
      )}

      <form className="broker-editor" onSubmit={save}>
        <div className="broker-editor-heading">
          <div><h3>账户凭证</h3><p>账号和交易密码只写入，不会从服务端返回。</p></div>
          {config.accountHint && <span className="broker-account-hint">已保存账号 {config.accountHint}</span>}
        </div>
        <div className="broker-form-grid">
          <label className="model-field">
            <span className="model-field-label">资金账号</span>
            <input
              type="text"
              value={accountNo}
              onChange={(event) => setAccountNo(event.target.value)}
              placeholder={config.accountConfigured ? "已保存，留空以保留当前账号" : "输入东方财富资金账号"}
              autoComplete="off"
              required={!config.accountConfigured}
            />
            <small>{config.accountConfigured ? `服务端仅显示尾号 ${config.accountHint.slice(-4)}。` : "账号会使用本机密钥加密后保存。"}</small>
          </label>
          <label className="model-field">
            <span className="model-field-label">交易密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={config.passwordConfigured ? "已保存，留空以保留当前密码" : "输入交易密码"}
              autoComplete="new-password"
              required={!config.passwordConfigured}
            />
            <small>{config.passwordConfigured ? "密码已加密保存；输入新密码可替换。" : "密码只写入，保存后不会回显。"}</small>
          </label>
          <label className="model-field broker-session-field">
            <span className="model-field-label">本地登录会话文件</span>
            <input
              type="text"
              value={sessionFile}
              onChange={(event) => setSessionFile(event.target.value)}
              placeholder="data/eastmoney_trader.session"
              required
            />
            <small>本机文件路径，不会上传会话文件内容。</small>
          </label>
        </div>

        {loading && <p className="broker-loading">正在读取已保存配置…</p>}
        {error && <div className="model-feedback error" role="alert">{error}</div>}
        {message && <div className="model-feedback success" role="status">{message}</div>}

        <div className="broker-editor-footer">
          <span>保存凭证不会开启实盘交易。</span>
          <button type="submit" className="model-primary" disabled={saving || loading}>{saving ? "正在保存…" : "保存券商配置"}</button>
        </div>
      </form>
    </div>
  );
}
