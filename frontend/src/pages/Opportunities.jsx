import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../api.js";
import { Spinner, ErrorBox, fmt, decisionClass } from "../components/ui.jsx";

export default function Opportunities() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    api
      .opportunities(100)
      .then((d) => alive && setRows(d.opportunities || []))
      .catch((e) => alive && setError(apiErrorMessage(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} />;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Sector</th>
            <th>Decision</th>
            <th className="num">Close</th>
            <th className="num">Chg %</th>
            <th className="num">Buy Prob</th>
            <th className="num">Stop</th>
            <th className="num">Target 1</th>
            <th className="num">Target 2</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const chg = Number(r.change_pct);
            return (
              <tr key={i}>
                <td>
                  <b>{r.symbol}</b>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {r.company}
                  </div>
                </td>
                <td className="muted">{r.sector}</td>
                <td>
                  <span className={`badge ${decisionClass(r.final_decision)}`}>
                    {r.final_decision}
                  </span>
                </td>
                <td className="num">{fmt(r.close)}</td>
                <td className={`num ${chg >= 0 ? "pos" : "neg"}`}>{fmt(chg)}</td>
                <td className="num">{fmt(r.buy_probability, 1)}</td>
                <td className="num">{fmt(r.stop_loss)}</td>
                <td className="num">{fmt(r.target_1)}</td>
                <td className="num">{fmt(r.target_2)}</td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={9} className="muted" style={{ textAlign: "center", padding: 24 }}>
                No opportunities in the latest scan.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
