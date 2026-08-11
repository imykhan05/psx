import { useState } from "react";
import { api, apiErrorMessage, getApiKey, setApiKey, getBaseUrl, setBaseUrl } from "../api.js";

export default function Settings({ onSaved }) {
  const [key, setKey] = useState(getApiKey());
  const [base, setBase] = useState(getBaseUrl());
  const [status, setStatus] = useState("");
  const [testing, setTesting] = useState(false);

  const save = () => {
    setApiKey(key.trim());
    setBaseUrl(base.trim());
    setStatus("Saved to this browser.");
    onSaved?.();
  };

  const test = async () => {
    setApiKey(key.trim());
    setBaseUrl(base.trim());
    setTesting(true);
    setStatus("");
    try {
      const h = await api.health();
      // /signal requires the key — this validates the key too.
      await api.signal();
      setStatus(`Connected ✓  (${h.service} v${h.version})`);
      onSaved?.();
    } catch (err) {
      setStatus(`Connection failed: ${apiErrorMessage(err)}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <div className="kpi label" style={{ marginBottom: 12 }}>
        Connection settings
      </div>
      <label className="field">
        <span>API base URL</span>
        <input className="input" value={base} onChange={(e) => setBase(e.target.value)} />
      </label>
      <label className="field">
        <span>API key (sent as X-API-Key)</span>
        <input
          className="input"
          type="password"
          placeholder="psx-dev-key-change-me"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
      </label>
      <div className="row">
        <button className="btn primary" onClick={save}>
          Save
        </button>
        <button className="btn" onClick={test} disabled={testing}>
          {testing ? "Testing…" : "Test connection"}
        </button>
      </div>
      {status && (
        <div className="muted" style={{ marginTop: 14, fontSize: 13 }}>
          {status}
        </div>
      )}
      <div className="muted" style={{ marginTop: 16, fontSize: 12 }}>
        The key is stored only in this browser (localStorage). It is never sent anywhere except your
        own API.
      </div>
    </div>
  );
}
