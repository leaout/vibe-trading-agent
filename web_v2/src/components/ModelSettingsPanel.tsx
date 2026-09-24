import { useState } from "react";

import { apiClient } from "../api/client";
import type { ModelStatus } from "../types";

interface ModelSettingsPanelProps {
  status: ModelStatus | null;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}

export function ModelSettingsPanel({ status, onClose, onRefresh }: ModelSettingsPanelProps) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState("");

  const testConnection = async () => {
    setTesting(true);
    setResult("");
    try {
      const response = await apiClient.testModel();
      setResult(response.message);
      await onRefresh();
    } catch (reason) {
      setResult(reason instanceof Error ? reason.message : "连接测试失败");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="create-backdrop" onMouseDown={onClose}>
      <section className="create-dialog model-dialog" onMouseDown={(event) => event.stopPropagation()}>
        <p className="eyebrow">AI DECISION ENGINE</p>
        <h2>决策模型</h2>
        <p>密钥只从后端环境变量读取，不会保存到浏览器。模型仅复核候选信号，仓位和风控由系统确定。</p>
        <div className="model-status-grid">
          <span><small>提供方</small><strong>{status?.provider ?? "—"}</strong></span>
          <span><small>模型</small><strong>{status?.model ?? "—"}</strong></span>
          <span><small>决策引擎</small><strong>{status?.decisionEnabled ? "已启用" : "未启用"}</strong></span>
          <span><small>最低置信度</small><strong>{status ? `${Math.round(status.minimumConfidence * 100)}%` : "—"}</strong></span>
        </div>
        <div className={`model-key-state ${status?.configured ? "configured" : ""}`}>
          <i />
          <div>
            <strong>{status?.configured ? "API 密钥已加载" : "等待 API 密钥"}</strong>
            <small>在后端设置 <code>{status?.apiKeyEnv ?? "MODEL_API_KEY"}</code> 后重启服务</small>
          </div>
        </div>
        <p className="model-safety-note">连接失败、超时、格式错误或置信度不足时，系统会安全回退为 HOLD，不会创建订单。</p>
        {result && <p className="model-test-result">{result}</p>}
        <div className="create-actions">
          <button className="cancel" onClick={onClose}>关闭</button>
          <button onClick={testConnection} disabled={!status?.configured || testing}>
            {testing ? "正在验证…" : "测试连接"}
          </button>
        </div>
      </section>
    </div>
  );
}
