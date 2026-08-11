from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


VERSION = "opportunity_ranking_engine_v1_0_institutional"


class OpportunityRankingEngineV1:
    def __init__(self, output_folder: str = "reports/opportunity_ranking"):
        self.output = Path(output_folder)
        self.output.mkdir(parents=True, exist_ok=True)

        self.ranked_path = self.output / "opportunity_ranking.csv"
        self.summary_path = self.output / "opportunity_ranking_summary.csv"
        self.categories_path = self.output / "opportunity_categories.csv"
        self.top_today_path = self.output / "top_opportunities_today.csv"
        self.watchlist_path = self.output / "opportunity_watchlist.csv"
        self.json_path = self.output / "opportunity_ranking.json"
        self.md_path = self.output / "opportunity_ranking.md"
        self.html_path = self.output / "opportunity_ranking.html"

    def run(
        self,
        market_df: pd.DataFrame,
        market_breadth_summary: dict | None = None,
        smart_money_summary: dict | None = None,
        portfolio_df: pd.DataFrame | None = None,
        trading_date: str | None = None,
        max_price: float = 500.0,
    ) -> dict:
        market_df = clean_df(market_df)
        portfolio_df = clean_df(portfolio_df)
        breadth = market_breadth_summary or {}
        smart = smart_money_summary or {}
        date = normalize_date(trading_date)

        ranked = self._rank(
            market_df,
            portfolio_df,
            breadth,
            smart,
            max_price,
        )
        categories = self._categories(ranked)
        summary = self._summary(ranked, categories, date)

        actionable = ranked[
            ranked["execution_bucket"].isin(
                ["BUY TODAY", "READY TO BUY"]
            )
        ].copy() if not ranked.empty else ranked.copy()

        watchlist = ranked[
            ranked["execution_bucket"].isin(
                ["WATCH", "WAIT FOR BREAKOUT", "WAIT FOR PULLBACK"]
            )
        ].copy() if not ranked.empty else ranked.copy()

        save_csv(ranked, self.ranked_path, self.ranked_columns())
        save_csv(categories, self.categories_path, self.category_columns())
        save_csv(actionable, self.top_today_path, self.ranked_columns())
        save_csv(watchlist, self.watchlist_path, self.ranked_columns())
        pd.DataFrame([summary]).to_csv(
            self.summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        payload = {
            "engine_version": VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "category_winners": categories.to_dict(orient="records"),
            "top_opportunities": ranked.head(30).to_dict(orient="records"),
        }
        self.json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.md_path.write_text(
            self._markdown(summary, ranked, categories),
            encoding="utf-8",
        )
        self.html_path.write_text(
            self._html(summary, ranked, categories),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "engine_version": VERSION,
            "trading_date": date,
            "opportunities_ranked": int(len(ranked)),
            "buy_today_count": int(
                ranked["execution_bucket"].eq("BUY TODAY").sum()
            ) if not ranked.empty else 0,
            "watch_count": int(
                ranked["execution_bucket"].str.contains(
                    "WATCH|WAIT", regex=True, na=False
                ).sum()
            ) if not ranked.empty else 0,
            "best_trade_today": summary["best_trade_today"],
            "best_swing_trade": summary["best_swing_trade"],
            "best_breakout_trade": summary["best_breakout_trade"],
            "best_low_risk_trade": summary["best_low_risk_trade"],
            "best_institutional_trade": summary["best_institutional_trade"],
            "ranked_csv": str(self.ranked_path),
            "summary_csv": str(self.summary_path),
            "categories_csv": str(self.categories_path),
            "top_today_csv": str(self.top_today_path),
            "watchlist_csv": str(self.watchlist_path),
            "json": str(self.json_path),
            "markdown": str(self.md_path),
            "html": str(self.html_path),
            "reason": "Opportunity ranking generated successfully",
        }

    def _rank(
        self,
        df: pd.DataFrame,
        portfolio_df: pd.DataFrame,
        breadth: dict,
        smart: dict,
        max_price: float,
    ) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=self.ranked_columns())

        x = df.copy()
        text_defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "final_decision": "",
            "risk_permission": "",
            "risk_status": "",
            "entry_timing_action": "",
            "lifecycle_status": "",
            "portfolio_position_status": "",
        }
        for col, default in text_defaults.items():
            if col not in x.columns:
                x[col] = default
            x[col] = x[col].fillna(default).astype(str).str.strip()

        x["symbol"] = x["symbol"].str.upper()
        x["sector"] = x["sector"].str.upper().replace("", "UNKNOWN")

        close = num(x, "close")
        change = num(x, "change_pct")
        volume = num(x, "volume")
        final_score = first_num(x, ["final_score", "ai_score_v5", "ai_score"])
        probability = first_num(x, ["buy_probability"])
        smart_score = first_num(x, ["smart_money_score_v2", "smart_money_score"])
        validation = first_num(x, ["trade_validation_score"])
        trend = first_num(x, ["trend_score_v5", "trend_score_v4", "trend_score"])
        volume_ratio = first_num(x, ["volume_ratio"])
        rsi = first_num(x, ["rsi_14", "rsi"])
        entry = first_num(
            x,
            ["adjusted_entry_price", "suggested_entry_price", "entry_price", "close"],
        )
        stop = first_num(x, ["stop_loss", "initial_stop_loss"])
        target1 = first_num(x, ["target_1"])
        target2 = first_num(x, ["target_2"])

        rr = ((target1 - entry).clip(lower=0) / (entry - stop).clip(lower=0).replace(0, pd.NA)).fillna(0)
        existing_rr = first_num(x, ["risk_reward_ratio"])
        rr = rr.where(rr.gt(0), existing_rr)

        decision = x["final_decision"].str.upper()
        permission = x["risk_permission"].str.upper()
        risk_status = x["risk_status"].str.upper()
        timing = x["entry_timing_action"].str.upper()
        lifecycle = x["lifecycle_status"].str.upper()
        portfolio_status = x["portfolio_position_status"].str.upper()

        decision_score = decision.map(
            {
                "BUY": 100,
                "HOLD": 60,
                "WATCH": 55,
                "AVOID": 10,
                "SELL": 0,
                "NO TRADE": 0,
            }
        ).fillna(25).astype(float)

        risk_score = permission.map(
            {
                "TRADE ALLOWED": 100,
                "TRADE ALLOWED SMALL": 85,
                "WAIT": 60,
                "NO TRADE": 0,
            }
        ).fillna(50).astype(float)

        risk_score = risk_score.where(
            ~risk_status.str.contains("CONTROLLED", na=False),
            90,
        )
        risk_score = risk_score.where(
            ~risk_status.str.contains("MEDIUM", na=False),
            65,
        )
        risk_score = risk_score.where(
            ~risk_status.str.contains(
                "HIGH|CHASE|REJECTED",
                regex=True,
                na=False,
            ),
            15,
        )

        timing_score = timing.map(
            {
                "BUY NOW": 100,
                "READY TO BUY": 95,
                "WAIT FOR BREAKOUT": 70,
                "WAIT FOR PULLBACK": 65,
                "WATCH": 55,
                "NO ENTRY": 0,
            }
        ).fillna(40).astype(float)

        portfolio_symbols = set()
        if not portfolio_df.empty and "symbol" in portfolio_df.columns:
            portfolio_symbols = set(
                portfolio_df["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

        portfolio_bonus = x["symbol"].isin(portfolio_symbols).astype(float) * 100
        portfolio_bonus = portfolio_bonus.where(
            ~portfolio_status.str.contains("READY TO BUY|OPEN", regex=True, na=False),
            100,
        )
        portfolio_bonus = portfolio_bonus.where(
            ~lifecycle.str.contains("READY TO BUY|OPEN", regex=True, na=False),
            100,
        )

        momentum = weighted(
            [
                (trend.clip(0, 100), 0.45),
                (scale(volume_ratio, 0, 3), 0.25),
                (scale(rsi, 35, 70), 0.15),
                (scale(change, -3, 8), 0.15),
            ]
        )
        rr_score = rr.clip(0, 4) / 4 * 100

        context = (
            safe_float(breadth.get("breadth_score", 50)) * 0.55
            + safe_float(smart.get("market_smart_money_score", 50)) * 0.45
        )

        score = weighted(
            [
                (final_score.clip(0, 100), 0.18),
                (probability.clip(0, 100), 0.16),
                (smart_score.clip(0, 100), 0.14),
                (validation.clip(0, 100), 0.12),
                (decision_score.clip(0, 100), 0.10),
                (risk_score.clip(0, 100), 0.10),
                (timing_score.clip(0, 100), 0.08),
                (rr_score.clip(0, 100), 0.05),
                (momentum.clip(0, 100), 0.04),
                (portfolio_bonus.clip(0, 100), 0.03),
            ]
        )

        score = (score * (0.85 + context / 100 * 0.30)).clip(0, 100)
        score = score.where(close.le(max_price) & close.gt(0), score * 0.20)
        score = score.where(
            ~decision.isin(["AVOID", "SELL", "NO TRADE"]),
            score * 0.35,
        )
        score = score.where(~permission.eq("NO TRADE"), score * 0.25)

        result = pd.DataFrame(
            {
                "symbol": x["symbol"],
                "company": x["company"],
                "sector": x["sector"],
                "close": close,
                "change_pct": change,
                "volume": volume,
                "final_decision": decision,
                "final_score": final_score,
                "buy_probability": probability,
                "smart_money_score": smart_score,
                "trade_validation_score": validation,
                "trend_score": trend,
                "risk_permission": permission,
                "risk_status": risk_status,
                "entry_timing_action": timing,
                "lifecycle_status": lifecycle,
                "portfolio_position_status": portfolio_status,
                "entry_price": entry,
                "stop_loss": stop,
                "target_1": target1,
                "target_2": target2,
                "reward_risk_ratio": rr,
                "decision_score": decision_score,
                "risk_score": risk_score,
                "entry_readiness_score": timing_score,
                "momentum_score": momentum,
                "portfolio_bonus": portfolio_bonus,
                "market_context_score": context,
                "opportunity_score": score,
            }
        )

        result["execution_bucket"] = result.apply(execution_bucket, axis=1)
        result["opportunity_grade"] = result["opportunity_score"].apply(grade)
        result["opportunity_type"] = result.apply(opportunity_type, axis=1)
        result["eligible_for_trade"] = result["execution_bucket"].isin(
            ["BUY TODAY", "READY TO BUY"]
        )
        result["ranking_reason"] = result.apply(reason, axis=1)

        result = result.sort_values(
            ["opportunity_score", "buy_probability", "trade_validation_score"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        result.insert(0, "overall_rank", range(1, len(result) + 1))

        return result[self.ranked_columns()]

    def _categories(self, ranked: pd.DataFrame) -> pd.DataFrame:
        if ranked.empty:
            return pd.DataFrame(columns=self.category_columns())

        groups = [
            (
                "BEST TRADE TODAY",
                ranked[ranked["execution_bucket"].isin(["BUY TODAY", "READY TO BUY"])],
            ),
            (
                "BEST SWING TRADE",
                ranked[ranked["opportunity_type"].str.contains("SWING", na=False)],
            ),
            (
                "BEST BREAKOUT TRADE",
                ranked[ranked["opportunity_type"].eq("BREAKOUT")],
            ),
            (
                "BEST LOW RISK TRADE",
                ranked[ranked["risk_score"].ge(80)],
            ),
            (
                "BEST INSTITUTIONAL PICK",
                ranked[ranked["smart_money_score"].ge(70)],
            ),
            (
                "BEST MOMENTUM TRADE",
                ranked[ranked["momentum_score"].ge(65)],
            ),
            (
                "BEST WATCHLIST CANDIDATE",
                ranked[
                    ranked["execution_bucket"].str.contains(
                        "WATCH|WAIT",
                        regex=True,
                        na=False,
                    )
                ],
            ),
        ]

        rows = []
        for category, group in groups:
            if group.empty:
                rows.append(
                    {
                        "category": category,
                        "symbol": "",
                        "company": "",
                        "sector": "",
                        "opportunity_score": 0.0,
                        "buy_probability": 0.0,
                        "smart_money_score": 0.0,
                        "risk_score": 0.0,
                        "execution_bucket": "NO CANDIDATE",
                        "reason": "No candidate met the category rules.",
                    }
                )
                continue

            row = group.iloc[0]
            rows.append(
                {
                    "category": category,
                    "symbol": text(row.get("symbol")),
                    "company": text(row.get("company")),
                    "sector": text(row.get("sector")),
                    "opportunity_score": round(safe_float(row.get("opportunity_score")), 2),
                    "buy_probability": round(safe_float(row.get("buy_probability")), 2),
                    "smart_money_score": round(safe_float(row.get("smart_money_score")), 2),
                    "risk_score": round(safe_float(row.get("risk_score")), 2),
                    "execution_bucket": text(row.get("execution_bucket")),
                    "reason": text(row.get("ranking_reason")),
                }
            )

        return pd.DataFrame(rows)[self.category_columns()]

    def _summary(
        self,
        ranked: pd.DataFrame,
        categories: pd.DataFrame,
        date: str,
    ) -> dict:
        lookup = {}
        if not categories.empty:
            lookup = dict(
                zip(
                    categories["category"].astype(str),
                    categories["symbol"].astype(str),
                )
            )

        return {
            "engine_version": VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "trading_date": date,
            "total_ranked": int(len(ranked)),
            "buy_today_count": int(
                ranked["execution_bucket"].eq("BUY TODAY").sum()
            ) if not ranked.empty else 0,
            "ready_to_buy_count": int(
                ranked["execution_bucket"].eq("READY TO BUY").sum()
            ) if not ranked.empty else 0,
            "watch_count": int(
                ranked["execution_bucket"].str.contains(
                    "WATCH|WAIT",
                    regex=True,
                    na=False,
                ).sum()
            ) if not ranked.empty else 0,
            "best_trade_today": lookup.get("BEST TRADE TODAY", ""),
            "best_swing_trade": lookup.get("BEST SWING TRADE", ""),
            "best_breakout_trade": lookup.get("BEST BREAKOUT TRADE", ""),
            "best_low_risk_trade": lookup.get("BEST LOW RISK TRADE", ""),
            "best_institutional_trade": lookup.get("BEST INSTITUTIONAL PICK", ""),
            "best_momentum_trade": lookup.get("BEST MOMENTUM TRADE", ""),
            "best_watchlist_candidate": lookup.get("BEST WATCHLIST CANDIDATE", ""),
            "top_opportunity_score": round(
                safe_float(ranked.iloc[0].get("opportunity_score")),
                2,
            ) if not ranked.empty else 0.0,
            "top_opportunity_grade": text(
                ranked.iloc[0].get("opportunity_grade")
            ) if not ranked.empty else "",
        }

    def _markdown(
        self,
        summary: dict,
        ranked: pd.DataFrame,
        categories: pd.DataFrame,
    ) -> str:
        lines = [
            "# Opportunity Ranking Engine V1",
            "",
            f"- Trading Date: **{summary['trading_date']}**",
            f"- Best Trade Today: **{summary['best_trade_today'] or 'None'}**",
            f"- Best Swing Trade: **{summary['best_swing_trade'] or 'None'}**",
            f"- Best Breakout Trade: **{summary['best_breakout_trade'] or 'None'}**",
            f"- Best Low-Risk Trade: **{summary['best_low_risk_trade'] or 'None'}**",
            f"- Best Institutional Pick: **{summary['best_institutional_trade'] or 'None'}**",
            "",
            "## Category Winners",
            "",
        ]

        for _, row in categories.iterrows():
            lines.append(
                f"- **{text(row.get('category'))}: "
                f"{text(row.get('symbol')) or 'None'}** — "
                f"{safe_float(row.get('opportunity_score')):.1f}/100"
            )

        lines.extend(["", "## Top Opportunities", ""])
        for _, row in ranked.head(15).iterrows():
            lines.append(
                f"{safe_int(row.get('overall_rank'))}. "
                f"**{text(row.get('symbol'))}** — "
                f"{safe_float(row.get('opportunity_score')):.1f}/100 | "
                f"{text(row.get('execution_bucket'))} | "
                f"{text(row.get('opportunity_grade'))}"
            )
        return "\n".join(lines)

    def _html(
        self,
        summary: dict,
        ranked: pd.DataFrame,
        categories: pd.DataFrame,
    ) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opportunity Ranking Engine V1</title>
<style>
body{{margin:0;background:#06101c;color:#eef5fb;font-family:Arial,sans-serif}}
.container{{width:min(1450px,96%);margin:24px auto}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{background:#0e1d2e;border:1px solid #21415f;border-radius:14px;padding:16px}}
.full{{grid-column:span 4}}
.label{{color:#91a8bd;font-size:11px;text-transform:uppercase}}
.value{{font-size:23px;font-weight:700;margin-top:7px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th,td{{padding:8px;border-bottom:1px solid #21415f;text-align:left}}
th{{color:#91a8bd}}
@media(max-width:850px){{.grid{{grid-template-columns:1fr 1fr}}.full{{grid-column:span 2}}}}
</style>
</head>
<body>
<div class="container">
<h1>PSX Opportunity Ranking Engine V1</h1>
<p>Trading Date: {esc(summary['trading_date'])}</p>
<div class="grid">
{card("Best Trade Today", summary["best_trade_today"] or "None")}
{card("Best Swing", summary["best_swing_trade"] or "None")}
{card("Best Breakout", summary["best_breakout_trade"] or "None")}
{card("Best Low Risk", summary["best_low_risk_trade"] or "None")}
<div class="card full">
<h2>Category Winners</h2>
{table(categories, self.category_columns(), 20)}
</div>
<div class="card full">
<h2>Ranked Opportunities</h2>
{table(ranked, [
    "overall_rank","symbol","company","sector","close","final_decision",
    "buy_probability","smart_money_score","trade_validation_score",
    "risk_permission","entry_timing_action","reward_risk_ratio",
    "opportunity_score","opportunity_grade","execution_bucket",
    "opportunity_type","ranking_reason"
], 50)}
</div>
</div>
</div>
</body>
</html>"""

    @staticmethod
    def ranked_columns() -> list[str]:
        return [
            "overall_rank","symbol","company","sector","close","change_pct",
            "volume","final_decision","final_score","buy_probability",
            "smart_money_score","trade_validation_score","trend_score",
            "risk_permission","risk_status","entry_timing_action",
            "lifecycle_status","portfolio_position_status","entry_price",
            "stop_loss","target_1","target_2","reward_risk_ratio",
            "decision_score","risk_score","entry_readiness_score",
            "momentum_score","portfolio_bonus","market_context_score",
            "opportunity_score","opportunity_grade","execution_bucket",
            "opportunity_type","eligible_for_trade","ranking_reason",
        ]

    @staticmethod
    def category_columns() -> list[str]:
        return [
            "category","symbol","company","sector","opportunity_score",
            "buy_probability","smart_money_score","risk_score",
            "execution_bucket","reason",
        ]


def run_opportunity_ranking_engine_v1(
    market_df: pd.DataFrame,
    market_breadth_summary: dict | None = None,
    smart_money_summary: dict | None = None,
    portfolio_df: pd.DataFrame | None = None,
    trading_date: str | None = None,
    max_price: float = 500.0,
    output_folder: str = "reports/opportunity_ranking",
) -> dict:
    return OpportunityRankingEngineV1(
        output_folder=output_folder
    ).run(
        market_df=market_df,
        market_breadth_summary=market_breadth_summary,
        smart_money_summary=smart_money_summary,
        portfolio_df=portfolio_df,
        trading_date=trading_date,
        max_price=max_price,
    )


def clean_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    return df.loc[:, ~df.columns.duplicated()].copy()


def num(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty or column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def first_num(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    for column in columns:
        if column in df.columns:
            return num(df, column)
    return pd.Series(0.0, index=df.index, dtype=float)


def weighted(items: list[tuple[pd.Series, float]]) -> pd.Series:
    index = items[0][0].index
    result = pd.Series(0.0, index=index, dtype=float)
    total = 0.0
    for series, weight in items:
        if weight <= 0:
            continue
        result += pd.to_numeric(series, errors="coerce").fillna(0.0) * weight
        total += weight
    return result / total if total > 0 else result


def scale(series: pd.Series, lower: float, upper: float) -> pd.Series:
    if upper <= lower:
        return pd.Series(50.0, index=series.index, dtype=float)
    return ((series - lower) / (upper - lower) * 100).clip(0, 100)


def execution_bucket(row: pd.Series) -> str:
    decision = text(row.get("final_decision")).upper()
    permission = text(row.get("risk_permission")).upper()
    timing = text(row.get("entry_timing_action")).upper()
    lifecycle = text(row.get("lifecycle_status")).upper()
    score = safe_float(row.get("opportunity_score"))

    if (
        decision == "BUY"
        and permission in {"TRADE ALLOWED", "TRADE ALLOWED SMALL"}
        and timing == "BUY NOW"
        and score >= 70
    ):
        return "BUY TODAY"
    if lifecycle == "READY TO BUY":
        return "READY TO BUY"
    if decision == "BUY" and timing == "BUY NOW":
        return "WATCH"
    if "BREAKOUT" in timing:
        return "WAIT FOR BREAKOUT"
    if "PULLBACK" in timing:
        return "WAIT FOR PULLBACK"
    if decision == "BUY":
        return "WATCH"
    return "AVOID"


def grade(score: float) -> str:
    score = safe_float(score)
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B+"
    if score >= 55: return "B"
    if score >= 45: return "C"
    return "D"


def opportunity_type(row: pd.Series) -> str:
    timing = text(row.get("entry_timing_action")).upper()
    if "BREAKOUT" in timing:
        return "BREAKOUT"
    if safe_float(row.get("smart_money_score")) >= 80:
        return "INSTITUTIONAL SWING"
    if safe_float(row.get("momentum_score")) >= 75:
        return "MOMENTUM SWING"
    if safe_float(row.get("risk_score")) >= 85:
        return "LOW RISK SWING"
    return "SWING"


def reason(row: pd.Series) -> str:
    return " | ".join(
        [
            f"Score {safe_float(row.get('opportunity_score')):.1f}",
            f"Buy probability {safe_float(row.get('buy_probability')):.1f}%",
            f"Smart money {safe_float(row.get('smart_money_score')):.1f}",
            f"Validation {safe_float(row.get('trade_validation_score')):.1f}",
            f"Risk score {safe_float(row.get('risk_score')):.1f}",
            f"Entry {text(row.get('entry_timing_action'))}",
        ]
    )


def save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    df = clean_df(df)
    if df.empty:
        pd.DataFrame(columns=columns).to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )
        return
    for column in columns:
        if column not in df.columns:
            df[column] = False if column == "eligible_for_trade" else ""
    df[columns].to_csv(path, index=False, encoding="utf-8-sig")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def normalize_date(value: Any) -> str:
    candidate = text(value)
    if not candidate:
        return datetime.now().strftime("%Y-%m-%d")
    parsed = pd.to_datetime(candidate, errors="coerce")
    return candidate if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def esc(value: Any) -> str:
    return html.escape(text(value))


def card(label: str, value: Any) -> str:
    return (
        "<div class='card'>"
        f"<div class='label'>{esc(label)}</div>"
        f"<div class='value'>{esc(value)}</div>"
        "</div>"
    )


def table(df: pd.DataFrame, columns: list[str], rows: int) -> str:
    if df.empty:
        return "<p>No records found.</p>"
    available = [column for column in columns if column in df.columns]
    header = "".join(
        f"<th>{esc(column.replace('_', ' ').title())}</th>"
        for column in available
    )
    body = []
    for _, row in df[available].head(rows).iterrows():
        cells = []
        for column in available:
            value = row.get(column, "")
            try:
                number = float(value)
                display = f"{number:.2f}" if not number.is_integer() else str(int(number))
            except Exception:
                display = text(value)
            cells.append(f"<td>{esc(display)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<div style='overflow:auto'><table><thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )
