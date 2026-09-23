import { FormEvent, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { AuthUser } from "../types";

interface Props { onAuthenticated: (user: AuthUser) => void; }

export function AuthScreen({ onAuthenticated }: Props) {
  const [registering, setRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try {
      const user = registering
        ? await apiClient.register(username, password)
        : await apiClient.login(username, password);
      onAuthenticated(user);
    } catch (reason) {
      const detail = reason instanceof ApiError
        && typeof reason.payload === "object"
        && reason.payload !== null
        && "detail" in reason.payload
        && typeof reason.payload.detail === "string"
        ? reason.payload.detail
        : undefined;
      if (detail?.includes("首次注册已完成")) setRegistering(false);
      setError(detail ?? (registering
        ? "注册失败：请确认这是首次注册且密码至少 8 位。"
        : "用户名或密码错误。"));
    } finally { setBusy(false); }
  };

  return <main className="auth-screen">
    <div className="auth-card">
      <div className="auth-brand"><div className="brand-mark"><span /></div><strong>VIBE<em>TRADING</em></strong></div>
      <p className="eyebrow">PRIVATE TRADING WORKSPACE</p>
      <h1>{registering ? "创建管理员账户" : "登录交易工作台"}</h1>
      <p className="auth-hint">{registering ? "首次启动请创建本地管理员账户。密码只保存为不可逆哈希。" : "登录后才能访问策略、行情和模拟账户。"}</p>
      <form onSubmit={submit}>
        <label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></label>
        <label>密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete={registering ? "new-password" : "current-password"} required /></label>
        {error && <p className="auth-error">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "处理中…" : registering ? "创建并登录" : "登录"}</button>
      </form>
      <button className="auth-switch" onClick={() => { setRegistering(!registering); setError(""); }}>
        {registering ? "已有账户？返回登录" : "首次使用？创建账户"}
      </button>
    </div>
  </main>;
}
