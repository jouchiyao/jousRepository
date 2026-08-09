"""报告生成：严格按「现象 → 归因 → 预测 → 策略」四层递进输出。"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from utils.semantic_mapper import labels_for


def _f(v, nd: int = 2) -> str:
    if v is None:
        return "—"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not math.isfinite(fv):
        return "—"
    return f"{fv:,.{nd}f}"


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:.1%}"


def _build_strategy(results: dict[str, Any], labels: dict[str, str]) -> list[str]:
    tips: list[str] = []
    flow = results.get("semantics", {}).get("_flow_type", "通用")
    is_dist = flow in ("配送", "配送/流向")
    delivery = results.get("semantics", {}).get("delivery") is not None
    pareto = results.get("pareto")
    if pareto and pareto.get("table") is not None and not pareto["table"].empty:
        group_label = labels.get("object", "关键项")
        measure_label = labels.get("measure_amount", "金额")
        k, share = pareto["k80"], pareto["top80_share"]
        tips.append(
            f"帕累托策略：前 {k} 个{group_label}贡献了 {share:.1%} 的{measure_label}，"
            "符合二八法则。建议将运营资源、补货优先级与促销预算向这些关键项集中，"
            "同时建立长尾项的自动化补货与淘汰机制。"
        )
    turnover = results.get("turnover")
    if turnover:
        days = turnover.get("days")
        if days is not None and len(days):
            latest = float(days.iloc[-1])
            mean = float(days.mean())
            tips.append(
                f"库存周转策略：当前周转天数约 {_f(latest)} 天（平均 {_f(mean)} 天）。"
                "若周转天数偏高，建议按 ABC 分类设置差异化安全库存、缩短补货周期；"
                "若偏低，注意防范缺货与效期风险。"
            )
        else:
            tips.append(
                f"库存周转策略：{turnover.get('method', '')}。建议补充库存快照字段后重算精确周转率。"
            )
    outliers = results.get("outliers") or {}
    if outliers:
        cols = "、".join(list(outliers.keys())[:3])
        n = sum(v["count"] for v in outliers.values())
        rules = "金额>0、数量上限、价格>0" + ("、时效区间" if delivery else "")
        tips.append(
            f"数据质量策略：共发现 {n} 个异常值（主要位于 {cols}）。"
            + f"建议建立 SQL 级校验规则（{rules}），在入库环节拦截异常，"
            + "并对已识别异常单独标记、单独分析，避免污染趋势判断。"
        )
    ts = results.get("ts")
    if ts and ts.get("slope") is not None:
        slope = ts["slope"]
        if slope > 0:
            tips.append(
                f"趋势策略：{labels.get('measure_amount', '核心指标')}呈上升趋势（斜率 {_f(slope)}/期）。"
                + (
                    "建议同步评估产能/库存/运力是否匹配，防止增长期缺货或履约超时；"
                    if is_dist
                    else "建议同步评估库存与补货能力是否匹配，防止增长期缺货与断货风险；"
                )
                + "对预测峰值月份提前备货。"
            )
        else:
            tips.append(
                f"趋势策略：{labels.get('measure_amount', '核心指标')}呈下降趋势（斜率 {_f(slope)}/期）。"
                + (
                    "建议下钻定位下滑最严重的区域/品类，排查竞品、价格、缺货与配送时效因素，"
                    if is_dist
                    else "建议下钻定位下滑最严重的区域/品类，排查竞品、价格、缺货与动销放缓因素，"
                )
                + "并针对 TOP 下滑项制定恢复计划。"
            )
    industry = results.get("semantics", {}).get("_industry", "通用")
    if industry == "医药":
        if is_dist:
            tips.append(
                "医药行业专属（配送口径）：重点关注药品效期与批号管理、冷链与配送时效合规、"
                "连锁总部集采与门店要货计划的联动，降低近效期损失与断货风险。"
            )
        else:
            tips.append(
                "医药行业专属（实销口径）：重点关注门店动销与断货预警、药品效期与批号管理、"
                "连锁总部要货计划与门店补货联动，降低近效期损失与缺货风险。"
            )
    elif industry == "物流":
        tips.append(
            "物流行业专属：以履约完成率/配送时效为核心 KPI，优化线路规划与波次调度，"
            "对超时率高的线路/承运商做专项复盘。"
        )
    elif industry in ("零售", "快消"):
        tips.append(
            "零售/快消专属：结合动销率与库存深度，对高动销低库存商品做自动补货预警，"
            "对低动销商品做清仓或陈列调整，避免滞销占用资金。"
        )
    if not tips:
        tips.append("策略建议：当前数据维度有限，建议补充时间、主体/客体、金额/数量字段后重新分析。")
    return tips


def build_report_md(results: dict[str, Any]) -> str:
    labels = labels_for(results.get("semantics", {}).get("_industry", "通用"))
    L: list[str] = []
    L.append("# 智能数据分析报告")
    L.append("")
    L.append(
        f"**数据规模**：{results['quality']['行数']:,} 行 × {results['quality']['列数']} 列　|　"
        f"**行业识别**：{results['semantics'].get('_industry', '通用')}　|　"
        f"**数据口径**：{results['semantics'].get('_flow_type', '通用')}　|　"
        f"**语义映射**：主体→{results['semantics'].get('subject') or '—'}，"
        f"客体→{results['semantics'].get('object') or '—'}，"
        f"时间→{results['semantics'].get('time') or '—'}，"
        f"金额→{results['semantics'].get('measure_amount') or '—'}，"
        f"数量→{results['semantics'].get('measure_qty') or '—'}"
    )
    L.append("")
    L.append("---")

    # ---------- 一、现象 ----------
    L.append("## 一、现象（发生了什么）")
    L.append("")
    q = results["quality"]
    L.append(
        f"- 数据共 **{q['行数']:,} 行**、**{q['列数']} 列**，重复行 {q['重复行']:,}，"
        f"缺失单元格 {q['缺失单元格']:,} 个，数值列 {q['数值列']} 个。"
    )
    desc = results["describe"]
    num_cols = results.get("numeric_cols") or []
    if num_cols:
        sample = desc[desc["类型"] == "数值"].head(3)
        for _, r in sample.iterrows():
            L.append(
                f"- 「{r['列名']}」：均值 {_f(r.get('均值'))}，标准差 {_f(r.get('标准差'))}，"
                f"范围 [{_f(r.get('最小'))}, {_f(r.get('最大'))}]，偏度 {_f(r.get('偏度'), 3)}，峰度 {_f(r.get('峰度'), 3)}"
            )
    outliers = results.get("outliers") or {}
    if outliers:
        L.append("")
        L.append("**异常洞察（IQR + 3-Sigma 复核）**：")
        for col, det in list(outliers.items())[:5]:
            L.append(f"- 「{col}」：{det['count']} 个异常（{det['method']}），" + "；".join(det["reasons"]))
    else:
        L.append("")
        L.append("**异常洞察**：未发现显著离群值。")
    L.append("")

    # ---------- 二、归因 ----------
    L.append("## 二、归因（为什么发生）")
    L.append("")
    pareto = results.get("pareto")
    if pareto and pareto.get("table") is not None and not pareto["table"].empty:
        L.append(
            f"**帕累托归因**：按「{results.get('pareto_group', '关键维度')}」聚合，"
            f"前 **{pareto['k80']}** 项累计贡献 **{pareto['top80_share']:.1%}**"
            f"（共 {pareto['n_groups']} 项），核心变量集中在头部。"
        )
        top5 = pareto["table"].head(5)
        for _, r in top5.iterrows():
            L.append(f"  - {r['项']}：{_f(r['值'])}（占比 {r['占比']:.1%}）")
    corr_top3 = results.get("corr_top3") or []
    if corr_top3:
        L.append("")
        L.append("**相关性归因（Top3）**：")
        from utils.analytics import explain_correlation

        for a, b, r in corr_top3:
            L.append(f"  - {explain_correlation(a, b, r)}")
    attr = results.get("anomaly_attribution") or {}
    if attr:
        L.append("")
        L.append("**异常聚集位置**：")
        for col, profs in list(attr.items())[:2]:
            for prof in profs[:3]:
                top = prof.iloc[0]
                L.append(f"  - 「{col}」的异常集中在 {top['维度']}={top['取值']}（{top['异常数']} 个）")
    monthly = results.get("monthly_trend")
    if monthly is not None and len(monthly):
        peak = monthly.loc[monthly["合计"].idxmax()]
        trough = monthly.loc[monthly["合计"].idxmin()]
        L.append("")
        L.append(
            f"**时间归因**：月度峰值出现在 {peak['月份']}（{_f(peak['合计'])}），"
            f"低谷在 {trough['月份']}（{_f(trough['合计'])}），存在明显的季节性波动。"
        )
    L.append("")

    # ---------- 三、预测 ----------
    L.append("## 三、预测（下一步会怎样）")
    L.append("")
    ts = results.get("ts")
    if ts:
        L.append(
            f"基于 {ts['freq_label']}序列、共 {ts['n']} 个周期，采用「{ts['model']}」拟合"
            f"（R²={ts['r2']:.2f}，趋势斜率 {_f(ts['slope'])}/期）。"
        )
        L.append("")
        L.append("未来 3 期预测：")
        for i, (idx, v) in enumerate(zip(ts["forecast_index"], ts["forecast"]), start=1):
            L.append(f"  - 第 {i} 期（{idx}）：**{_f(v)}**")
    else:
        L.append("时间字段或度量字段不足，无法进行时序预测。建议提供「日期 + 金额/数量」字段。")
    L.append("")

    # ---------- 四、策略 ----------
    L.append("## 四、策略（应该怎么办）")
    L.append("")
    for tip in _build_strategy(results, labels):
        L.append(f"- {tip}")
    L.append("")
    L.append("---")
    L.append("*本报告由数据分析工作台自动生成，遵循「现象 → 归因 → 预测 → 策略」四层递进逻辑。*")
    return "\n".join(L)
