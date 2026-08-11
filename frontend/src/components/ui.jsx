export function Spinner() {
  return <div className="spinner" aria-label="loading" />;
}

export function ErrorBox({ message }) {
  return <div className="errorbox">⚠ {message}</div>;
}

export function fmt(n, digits = 2) {
  if (n === null || n === undefined || n === "" || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function decisionClass(decision) {
  const d = String(decision || "").toUpperCase();
  if (d.includes("STRONG BUY") || d === "BUY" || d === "ACCUMULATE") return "buy";
  if (d.includes("WATCH") || d.includes("WAIT")) return "watch";
  return "avoid";
}

export const VERDICT_COLOR = {
  BULLISH: "var(--green)",
  BEARISH: "var(--red)",
  NEUTRAL: "var(--amber)",
};
