import { useState } from "react";
import { api, apiErrorMessage } from "../api.js";
import { Spinner, ErrorBox, fmt, decisionClass } from "../components/ui.jsx";

export default function StockLookup() {
  const [ticker, setTicker] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = (e) => {
    e?.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    setLoading(true);
    setError("");
    setData(null);
    api
      .stock(t)
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err)))
      .finally(() => setLoading(false));
  };

  return (
    <div className="grid" style={{ gap: 16 }}>
      <form className="row" onSubmit={search}>
        <input
          className="input"
          placeholder="Enter a PSX symbol, e.g. MCB, OGDC, LUCK"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
        />
        <button className="btn primary" type="submit" disabled={loading}>
          Search
        </button>
      </form>

      {loading && <Spinner />}
      {error && <ErrorBox message={error} />}

      {data && (
        <div className="grid cols-2" style={{ gap: 14 }}>
          <div className="card">
            <div className="kpi label">{data.symbol} · {data.sector}</div>
            <div style={{ fontSize: 15, marginTop: 2 }}>{data.company}</div>
            <div className="grid cols-2" style={{ marginTop: 14 }}>
              <div className="kpi">
                <span className="label">Close</span>
                <span className="value">{fmt(data.price?.close)}</span>
              </div>
              <div className="kpi">
                <span className="label">Change %</span>
                <span
                  className="value"
                  style={{ color: Number(data.price?.change_pct) >= 0 ? "var(--green)" : "var(--red)" }}
                >
                  {fmt(data.price?.change_pct)}
                </span>
              </div>
              <div className="kpi">
                <span className="label">Volume</span>
                <span className="value">{fmt(data.price?.volume, 0)}</span>
              </div>
              <div className="kpi">
                <span className="label">Date</span>
                <span className="value" style={{ fontSize: 16 }}>{data.price?.date || "—"}</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="kpi label">Scoring</div>
            <div style={{ margin: "8px 0 14px" }}>
              <span className={`badge ${decisionClass(data.scoring?.final_decision)}`}>
                {data.scoring?.final_decision}
              </span>{" "}
              <span className="muted" style={{ marginLeft: 8 }}>
                risk: {data.scoring?.risk_permission}
              </span>
            </div>
            <div className="grid cols-2">
              <div className="kpi"><span className="label">Buy probability</span><span className="value">{fmt(data.scoring?.buy_probability, 1)}</span></div>
              <div className="kpi"><span className="label">Smart money</span><span className="value">{fmt(data.scoring?.smart_money_score, 0)}</span></div>
              <div className="kpi"><span className="label">Stop loss</span><span className="value">{fmt(data.scoring?.stop_loss)}</span></div>
              <div className="kpi"><span className="label">Target 1</span><span className="value">{fmt(data.scoring?.target_1)}</span></div>
              <div className="kpi"><span className="label">Target 2</span><span className="value">{fmt(data.scoring?.target_2)}</span></div>
              <div className="kpi"><span className="label">Entry timing</span><span className="value" style={{ fontSize: 15 }}>{data.scoring?.entry_timing_action || "—"}</span></div>
            </div>
          </div>

          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <div className="kpi label">News sentiment</div>
            {data.news_sentiment ? (
              <div style={{ marginTop: 8 }}>
                <span
                  className={`badge ${
                    data.news_sentiment.sentiment_label === "BULLISH"
                      ? "buy"
                      : data.news_sentiment.sentiment_label === "BEARISH"
                      ? "avoid"
                      : "watch"
                  }`}
                >
                  {data.news_sentiment.sentiment_label}
                </span>
                <span className="muted" style={{ marginLeft: 10 }}>
                  score {fmt(data.news_sentiment.sentiment_score)} · {data.news_sentiment.n_headlines} headline(s)
                </span>
                <ul className="reasons" style={{ marginTop: 10 }}>
                  {(data.news_sentiment.sample_headlines || []).map((h, i) => (
                    <li key={i}>“{h.title}” — {h.source} ({h.label})</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="muted" style={{ marginTop: 8 }}>
                No news matched this ticker in today’s feeds.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
