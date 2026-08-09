"""分析引擎：描述性 / 诊断性 / 预测性 / 规范性四大支柱 + 异常洞察 + 相关性挖掘。

纯 pandas + numpy 实现，兼容 pandas 2.x / 3.x，无 statsmodels 硬依赖。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=[np.number]).columns.tolist()


_CODE_HINTS = ("code", "编码", "编号", "工号")


def analyzable_numeric_columns(df: pd.DataFrame) -> list[str]:
    """参与异常/相关分析的数值列：剔除编码、编号、工号类标识列（如 prod_code）。"""
    return [
        c
        for c in numeric_columns(df)
        if not any(h in str(c).lower() for h in _CODE_HINTS)
    ]


# ---------- 1. 描述性统计 ----------

def describe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(df)
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        if pd.api.types.is_numeric_dtype(s):
            kind = "数值"
        elif pd.api.types.is_datetime64_any_dtype(s):
            kind = "时间"
        else:
            kind = "文本"
        row = {
            "列名": col,
            "类型": kind,
            "非空": total - missing,
            "缺失": missing,
            "缺失率": f"{missing / total:.1%}" if total else "0%",
            "唯一值": int(s.nunique(dropna=True)),
        }
        if kind == "数值":
            num = pd.to_numeric(s, errors="coerce").dropna()
            if len(num):
                row.update(
                    {
                        "均值": round(float(num.mean()), 4),
                        "标准差": round(float(num.std(ddof=0)), 4),
                        "最小": round(float(num.min()), 4),
                        "Q1": round(float(num.quantile(0.25)), 4),
                        "中位数": round(float(num.median()), 4),
                        "Q3": round(float(num.quantile(0.75)), 4),
                        "最大": round(float(num.max()), 4),
                        "偏度": round(float(num.skew()), 3),
                        "峰度": round(float(num.kurt()), 3),
                    }
                )
        rows.append(row)
    return pd.DataFrame(rows)


def data_quality_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "行数": int(len(df)),
        "列数": int(df.shape[1]),
        "重复行": int(df.duplicated().sum()),
        "缺失单元格": int(df.isna().sum().sum()),
        "数值列": len(numeric_columns(df)),
    }


# ---------- 异常洞察 ----------

def detect_outliers(series: pd.Series, method: str = "iqr", k: float = 1.5) -> dict[str, Any]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 4:
        return {"count": 0, "low_count": 0, "high_count": 0, "bounds": None, "method": method, "reasons": []}
    if method == "iqr":
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
        label = "IQR 1.5 倍四分位距"
    else:
        mu, sd = float(s.mean()), float(s.std(ddof=0))
        lo, hi = mu - 3 * sd, mu + 3 * sd
        label = "3-Sigma 原则"
    low = s[s < lo]
    high = s[s > hi]
    reasons = []
    if len(low):
        reasons.append(f"{len(low)} 个低于下界 {round(lo, 2)}：可能为录入错误 / 退货冲减 / 促销低谷")
    if len(high):
        reasons.append(f"{len(high)} 个高于上界 {round(hi, 2)}：可能为大额订单 / 团购集中 / 数据异常")
    return {
        "count": int(len(low) + len(high)),
        "low_count": int(len(low)),
        "high_count": int(len(high)),
        "bounds": (round(lo, 2), round(hi, 2)),
        "method": label,
        "reasons": reasons,
    }


def anomaly_profile(df: pd.DataFrame, col: str, dim_cols: list[str]) -> list[pd.DataFrame]:
    """异常归因：异常值集中在哪些维度（区域/品类/主体）。"""
    s = pd.to_numeric(df[col], errors="coerce")
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    mask = (s < lo) | (s > hi)
    out = []
    for d in dim_cols:
        if d not in df.columns or d == col:
            continue
        g = df[mask].groupby(d, dropna=False).size().sort_values(ascending=False)
        if len(g):
            out.append(pd.DataFrame({"维度": d, "取值": g.index, "异常数": g.values}).head(6))
    return out


# ---------- 相关性挖掘 ----------

def correlation_analysis(df: pd.DataFrame):
    num_df = df[analyzable_numeric_columns(df)]
    if num_df.shape[1] < 2:
        return None, [], []
    corr = num_df.corr()
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.notna(v):
                pairs.append((cols[i], cols[j], float(v)))
    pairs.sort(key=lambda x: -abs(x[2]))
    return corr, pairs[:3], cols


def explain_correlation(a: str, b: str, r: float) -> str:
    strength = "强" if abs(r) >= 0.7 else ("中等强度" if abs(r) >= 0.4 else "弱")
    direction = "正相关（同升同降）" if r > 0 else "负相关（此消彼长）"
    return f"「{a}」与「{b}」呈{strength}{direction}（r={r:.3f}）"


# ---------- 诊断性：下钻与帕累托 ----------

def drilldown(df: pd.DataFrame, dim_col: str, value_col: str | None = None, agg: str = "sum", top_n: int = 15) -> pd.DataFrame:
    if value_col is None or value_col not in df.columns:
        g = df.groupby(dim_col, dropna=False).size().rename("计数")
        out = g.sort_values(ascending=False).head(top_n).reset_index()
        out["占比"] = out["计数"] / out["计数"].sum()
        out["累计占比"] = out["计数"].cumsum() / out["计数"].sum()
        return out
    g = df.groupby(dim_col, dropna=False)[value_col].agg(agg).sort_values(ascending=False)
    total = float(g.sum())
    out = g.head(top_n).reset_index()
    out["占比"] = out[value_col] / total if total else 0
    out["累计占比"] = out[value_col].cumsum() / total if total else 0
    return out


def time_bucket_table(df: pd.DataFrame, time_col: str, value_col: str) -> pd.DataFrame:
    d = df.copy()
    d["_t"] = pd.to_datetime(d[time_col], errors="coerce")
    d = d.dropna(subset=["_t"])
    d["月份"] = d["_t"].dt.to_period("M").astype(str)
    g = d.groupby("月份", dropna=False)[value_col].sum().sort_index()
    out = g.reset_index()
    out.columns = ["月份", "合计"]
    return out


def pareto(df: pd.DataFrame, group_col: str, value_col: str) -> dict[str, Any]:
    g = df.groupby(group_col, dropna=False)[value_col].sum().sort_values(ascending=False)
    total = float(g.sum())
    if total <= 0:
        return {"table": pd.DataFrame(), "k80": 0, "top80_share": 0.0, "total": total, "n_groups": int(len(g))}
    share = g.cumsum() / total
    k80 = next((i + 1 for i, v in enumerate(share) if v >= 0.8), len(g))
    table = pd.DataFrame(
        {
            "项": g.index,
            "值": g.values,
            "占比": g.values / total,
            "累计占比": share.values,
        }
    )
    return {
        "table": table,
        "k80": int(k80),
        "top80_share": float(share.iloc[min(k80, len(share)) - 1]),
        "total": total,
        "n_groups": int(len(g)),
    }


# ---------- 规范性：库存周转 ----------

def inventory_turnover(df: pd.DataFrame, time_col: str, qty_col: str, inventory_col: str | None = None) -> dict[str, Any]:
    if time_col not in df.columns or qty_col not in df.columns:
        return {"method": "缺少时间或数量列，无法计算周转"}
    d = df.copy()
    d["_t"] = pd.to_datetime(d[time_col], errors="coerce")
    d = d.dropna(subset=["_t", qty_col])
    d["月份"] = d["_t"].dt.to_period("M").astype(str)
    monthly = d.groupby("月份", dropna=False)[qty_col].sum().sort_index()
    if len(monthly) < 2:
        return {"method": "时间跨度不足，无法计算周转", "monthly": monthly}
    result: dict[str, Any] = {"method": "", "monthly": monthly}
    if inventory_col and inventory_col in df.columns:
        inv = d.groupby("月份", dropna=False)[inventory_col].mean()
        turnover = monthly / inv.replace(0, np.nan)
        days = 30.4 / turnover
        result.update(
            {
                "method": "库存周转率 = 月销量 / 月均库存；周转天数 ≈ 30.4 / 周转率",
                "turnover": turnover,
                "days": days,
            }
        )
    else:
        mean_month = float(monthly.mean()) or 1.0
        ratio = monthly / mean_month
        result.update(
            {
                "method": "未检测到库存列，使用动销强度（月销量/月均销量）作为周转代理指标",
                "turnover": ratio,
                "days": None,
            }
        )
    return result


# ---------- 预测性：时序分解 + 线性回归 ----------

def time_series_analysis(
    df: pd.DataFrame,
    time_col: str,
    measure_col: str,
    forecast_n: int = 3,
    freq: str | None = None,
) -> dict[str, Any] | None:
    """时序分解 + 线性回归预测。

    freq: None 自动识别；可选 D(日) / W(周) / ME(月) / YE(年)。
    返回含 series/trend/seasonal/remainder/forecast 等字段。
    """
    if time_col not in df.columns or measure_col not in df.columns:
        return None
    s = df[[time_col, measure_col]].copy()
    s["_t"] = pd.to_datetime(s[time_col], errors="coerce")
    s = s.dropna(subset=["_t", measure_col])
    s = s.set_index("_t")[measure_col].astype(float).sort_index()
    if len(s) < 4:
        return None
    if freq is None:
        diffs = (s.index[1:] - s.index[:-1]).days
        med = float(np.median(diffs)) if len(diffs) else 1.0
        freq = "D" if med <= 2 else ("W" if med <= 9 else "ME")
    else:
        freq = str(freq).upper()
        if freq == "M":
            freq = "ME"
        if freq == "Y":
            freq = "YE"
    ts = s.resample(freq).sum().fillna(0.0)
    if len(ts) < 2:
        return None

    window = min(len(ts), 7 if freq == "D" else (4 if freq == "W" else 3))
    if window % 2 == 0:
        window += 1
    trend = ts.rolling(window, center=True, min_periods=1).mean()
    detrended = ts - trend
    if freq == "YE":
        keys = pd.Series(ts.index.year, index=ts.index)
    elif freq == "D" or freq == "W":
        keys = pd.Series(ts.index.dayofweek, index=ts.index)
    else:
        keys = pd.Series(ts.index.month, index=ts.index)
    seasonal = detrended.groupby(keys).transform("mean").fillna(0.0)
    remainder = detrended - seasonal

    x = np.arange(len(ts), dtype=float)
    y = ts.values.astype(float)
    slope, intercept = np.polyfit(x, y, 1)
    r2 = float(np.corrcoef(x, y)[0, 1] ** 2) if len(x) > 1 else 0.0

    future_idx = pd.date_range(start=ts.index[-1], periods=forecast_n + 1, freq=freq)[1:]
    fc = []
    for k, fidx in enumerate(future_idx, start=1):
        base = intercept + slope * (len(ts) + k - 1)
        if freq == "ME":
            factor = float(seasonal[ts.index.month == fidx.month].iloc[-1]) if (ts.index.month == fidx.month).any() and len(seasonal[ts.index.month == fidx.month]) else 0.0
        elif freq == "YE":
            factor = 0.0
        else:
            factor = float(seasonal[ts.index.dayofweek == fidx.dayofweek].iloc[-1]) if (ts.index.dayofweek == fidx.dayofweek).any() and len(seasonal[ts.index.dayofweek == fidx.dayofweek]) else 0.0
        fc.append(round(float(max(base + factor, 0.0)), 2))

    return {
        "freq": freq,
        "freq_label": {"D": "按日", "W": "按周", "ME": "按月", "YE": "按年"}[freq],
        "series": ts,
        "trend": trend,
        "seasonal": seasonal,
        "remainder": remainder,
        "forecast_index": [str(i.date()) for i in future_idx],
        "forecast": fc,
        "slope": round(float(slope), 4),
        "r2": r2,
        "n": int(len(ts)),
        "model": "线性回归 + 周期均值季节调整（简易 STL 分解：移动平均趋势 + 季节项 + 残差）",
    }


# ---------- 主流水线 ----------

def run_analysis_pipeline(df: pd.DataFrame, semantics: dict[str, Any], forecast_n: int = 3) -> dict[str, Any]:
    """一键执行完整分析，输出供报告层消费的结构化结果。"""
    d = df.copy()
    tcol = semantics.get("time")
    if tcol and not pd.api.types.is_datetime64_any_dtype(d[tcol]):
        d[tcol] = pd.to_datetime(d[tcol], errors="coerce")
    for role in ("measure_amount", "measure_qty"):
        c = semantics.get(role)
        if c and c in d.columns and not pd.api.types.is_numeric_dtype(d[c]):
            d[c] = pd.to_numeric(
                d[c].astype(str).str.replace(",", "", regex=False).str.replace("元", "", regex=False),
                errors="coerce",
            )

    result: dict[str, Any] = {
        "describe": describe_dataframe(d),
        "quality": data_quality_summary(d),
        "semantics": semantics,
        "columns": list(d.columns),
    }

    # 异常洞察（每个数值列 IQR，另附 3-Sigma 复核）
    outliers = {}
    for col in analyzable_numeric_columns(d):
        det = detect_outliers(d[col], method="iqr")
        if det["count"]:
            det["col"] = col
            outliers[col] = det
    result["outliers"] = outliers

    # 异常归因（异常集中在哪些维度）
    dim_candidates = [
        semantics.get("space"),
        semantics.get("category"),
        semantics.get("subject"),
        semantics.get("status"),
    ]
    dims = [c for c in dim_candidates if c and c in d.columns]
    anomaly_attribution = {}
    for col in list(outliers.keys())[:3]:
        prof = anomaly_profile(d, col, dims)
        if prof:
            anomaly_attribution[col] = prof
    result["anomaly_attribution"] = anomaly_attribution

    # 相关性
    corr, top3, num_cols = correlation_analysis(d)
    result["corr"] = corr
    result["corr_top3"] = top3
    result["numeric_cols"] = num_cols

    # 下钻：按语义维度 × 金额/数量
    mcol = semantics.get("measure_amount") or semantics.get("measure_qty")
    drilldowns = {}
    for role, key in (
        ("subject", "主体"),
        ("object", "客体"),
        ("space", "空间"),
        ("category", "品类"),
        ("status", "状态"),
    ):
        c = semantics.get(role)
        if c and c in d.columns and mcol and mcol in d.columns:
            drilldowns[f"{key}-{c}"] = drilldown(d, c, mcol, agg="sum")
    result["drilldowns"] = drilldowns
    result["drilldown_dimensions"] = list(drilldowns.keys())

    # 帕累托（默认：客体 × 金额；无客体用第一个可分组列）
    pgroup = semantics.get("object") or semantics.get("subject") or semantics.get("category")
    if pgroup and mcol:
        result["pareto"] = pareto(d, pgroup, mcol)
        result["pareto_group"] = pgroup
    else:
        result["pareto"] = None
        result["pareto_group"] = None

    # 时序（默认：金额，无则数量）
    if tcol and mcol:
        # 默认按月度预测（用户可随时在界面切换为 日/周/年）
        result["ts"] = time_series_analysis(d, tcol, mcol, forecast_n=forecast_n, freq="ME")
    else:
        result["ts"] = None

    # 库存周转
    qcol = semantics.get("measure_qty")
    inv_col = next((c for c in d.columns if "库存" in str(c)), None)
    if tcol and qcol:
        result["turnover"] = inventory_turnover(d, tcol, qcol, inv_col)
    else:
        result["turnover"] = None

    # 时序下钻表（月趋势）
    if tcol and mcol:
        result["monthly_trend"] = time_bucket_table(d, tcol, mcol)
    else:
        result["monthly_trend"] = None

    result["df"] = d
    return result
