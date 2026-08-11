import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../api.js";
import { Spinner, ErrorBox, VERDICT_COLOR } from "../components/ui.jsx";

export default function Home() {
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    api
      .signal()
      .then((d) => alive && setSignal(d))
      .catch((e) => alive && setError(apiErrorMessage(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} />;
  if (!signal) return <ErrorBox message="No signal data." />;

  const color = VERDICT_COLOR[String(signal.verdict).toUpperCase()] || "var(--muted)";
  const confidence = Math.round((signal.confidence || 0) * 100);
  const s = signal.sentiment_summary || {};
  const b = signal.breadth || {};

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="card verdict-card">
        <p className="verdict-word" style={{ color }}>
          {signal.verdict}
        </p>
        <div className="verdict-meta">
          Confidence <b style={{ color }}>{confidence}%</b> &nbsp;·&nbsp; Trading date{" "}
          {signal.date}
        </div>
        <div className="chips">
          <span className="chip">
            Advancers <b>{b.advancers ?? "—"}</b> / Decliners <b>{b.decliners ?? "—"}</b>
          </span>
          <span className="chip">
            News: <b>{s.bullish ?? 0}</b> bullish, <b>{s.bearish ?? 0}</b> bearish,{" "}
            <b>{s.neutral ?? 0}</b> neutral
          </span>
        </div>
        <ul className="reasons">
          {(signal.reasons || []).map((r, i) => (
            <li key={i}>• {r}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <div className="kpi label" style={{ marginBottom: 10 }}>
          Top opportunities
        </div>
        <div className="chips">
          {(signal.top_opportunities || []).map((t) => (
            <span className="chip" key={t}>
              <b>{t}</b>
            </span>
          ))}
          {(!signal.top_opportunities || signal.top_opportunities.length === 0) && (
            <span className="muted">None flagged today.</span>
          )}
        </div>
        <div className="muted" style={{ marginTop: 16, fontSize: 12 }}>
          Generated {signal.generated_at} · decision-support from an end-of-day rule-based scan,
          not financial advice.
        </div>
      </div>
    </div>
  );
}
