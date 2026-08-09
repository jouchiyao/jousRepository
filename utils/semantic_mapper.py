"""语义映射层：把任意行业数据自动映射为通用语义（主体/客体/时间/度量/空间…）。

设计目标：不硬编码业务字段，医药、零售、快消、物流数据进入同一套分析管线。
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

# 角色 -> (关键词, 权重)。列名会先做归一化（小写、去空格下划线）。
ROLE_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "subject": [
        ("供应商", 5), ("批发商", 5), ("配送商", 5), ("仓库", 4), ("门店", 4),
        ("客户", 3), ("店铺", 3), ("连锁", 3), ("商户", 3), ("supplier", 5),
        ("vendor", 5), ("warehouse", 4), ("store", 4), ("shop", 4), ("customer", 3),
        ("seller", 3), ("org", 2), ("company", 2), ("distributor", 5),
        ("wholesaler", 5), ("cust", 4), ("customer", 5), ("downcust", 7),
        ("down_cust", 7), ("upcust", 6), ("up_cust", 6), ("groupcust", 5),
        ("group_cust", 5),
    ],
    "object": [
        ("sku", 6), ("商品", 5), ("产品", 5), ("药品", 5), ("物料", 5), ("货品", 5),
        ("品名", 4), ("名称", 3), ("product", 5), ("item", 4), ("goods", 4),
        ("drug", 5), ("medicine", 5), ("article", 4), ("prod", 6),
        ("productname", 6), ("generic", 3), ("drugname", 6), ("itemname", 5),
        ("prodname", 7),
    ],
    "time": [
        ("日期", 5), ("时间", 4), ("月份", 4), ("年月", 4), ("下单", 3), ("配送日", 3),
        ("发货", 3), ("销售日", 3), ("date", 5), ("time", 4), ("month", 4),
        ("day", 3), ("year", 3), ("period", 3), ("created", 3), ("order", 2),
        ("bizdate", 6), ("biz_date", 6), ("业务日期", 6), ("交易", 4),
    ],
    "space": [
        ("区域", 5), ("地区", 5), ("城市", 5), ("省份", 5), ("省市", 4), ("大区", 4),
        ("region", 5), ("city", 5), ("province", 5), ("area", 4), ("zone", 4),
        ("district", 4), ("address", 2), ("prov", 4), ("provname", 6),
        ("downprov", 7), ("down_prov", 7), ("upprov", 4), ("up_prov", 4),
        ("province_name", 6), ("cityname", 5),
    ],
    "measure_amount": [
        ("金额", 6), ("销售额", 6), ("营收", 5), ("收入", 4), ("成本", 4), ("利润", 5),
        ("毛利", 5), ("gmv", 6), ("amount", 6), ("sales", 5), ("revenue", 6),
        ("cost", 5), ("profit", 5), ("price", 4), ("金额元", 6), ("total", 4),
        ("totalprice", 7), ("total_price", 7), ("总额", 7), ("成交额", 6),
    ],
    "measure_qty": [
        ("数量", 6), ("销量", 6), ("件数", 5), ("箱数", 5), ("库存", 5), ("盒数", 5),
        ("入库", 4), ("出库", 4), ("quantity", 6), ("qty", 6), ("count", 4),
        ("stock", 5), ("inventory", 5), ("volume", 4), ("units", 4),
    ],
    "category": [
        ("分类", 5), ("类别", 5), ("品类", 5), ("类型", 4), ("品种", 4), ("sku分类", 5),
        ("category", 5), ("type", 4), ("class", 4), ("group", 3), ("品牌", 3), ("brand", 3),
    ],
    "status": [
        ("状态", 5), ("进度", 3), ("阶段", 3), ("status", 5), ("state", 4),
        ("is", 2), ("flag", 3),
    ],
    "delivery": [
        ("时效", 6), ("配送时效", 7), ("履约", 6), ("配送时长", 6), ("leadtime", 6),
        ("lead_time", 6), ("delivery", 5), ("fulfillment", 6), ("响应", 4),
        ("on_time", 5), ("准时", 5), ("签收", 4),
    ],
}

# 行业识别关键词
INDUSTRY_SIGNALS: dict[str, list[str]] = {
    "医药": ["药品", "药房", "药店", "医药", "医院", "处方", "医保", "连锁总部", "连锁", "配送商", "抗生素", "胶囊", "片剂", "注射", "gsp", "药监"],
    "零售": ["门店", "零售", "会员", "收银", "sku", "陈列", "促销", "店铺", "商场", "便利店", "专柜", "销量"],
    "快消": ["快消", "饮料", "食品", "日化", "铺货", "动销", "经销商", "cbd", "超市", "货架", "批次"],
    "物流": ["配送", "时效", "履约", "仓库", "干线", "城配", "承运", "物流", "运单", "签收", "发运", "线路", "车辆"],
}

# 行业标签适配：同一角色在不同行业展示不同的业务叫法
INDUSTRY_LABELS: dict[str, dict[str, str]] = {
    "医药": {
        "subject": "供应商", "object": "药品/SKU", "time": "配送日期", "space": "区域",
        "measure_amount": "金额", "measure_qty": "数量", "delivery": "配送时效",
    },
    "零售": {
        "subject": "门店", "object": "商品", "time": "销售日期", "space": "商圈/区域",
        "measure_amount": "销售额", "measure_qty": "销量", "delivery": "到货时效",
    },
    "快消": {
        "subject": "经销商/终端", "object": "SKU", "time": "铺货日期", "space": "渠道区域",
        "measure_amount": "销售额", "measure_qty": "动销量", "delivery": "补货周期",
    },
    "物流": {
        "subject": "承运方/仓库", "object": "运单/货物", "time": "发运日期", "space": "线路/区域",
        "measure_amount": "运费", "measure_qty": "件量", "delivery": "履约完成率",
    },
    "通用": {
        "subject": "主体", "object": "客体", "time": "时间", "space": "空间",
        "measure_amount": "金额", "measure_qty": "数量", "delivery": "时效/履约",
    },
}


def _norm(name: str) -> str:
    s = str(name).lower()
    s = re.sub(r"[\s_\-（）()\[\]【】/]", "", s)
    return s


def _is_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _tokens(name: str) -> list[str]:
    """把列名切成语义 token：下划线/括号/空格/驼峰边界。
    例：group_cust_name → [group, cust, name]；bizDate → [biz, date]。"""
    s = str(name)
    s = re.sub(r"[\s_\-/（）()\[\]【】.、]+", " ", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return [t.lower() for t in s.split() if t]


_SKIP_TOKENS = {"code", "编码", "编号", "id"}


def _score_column(name: str, keywords: list[tuple[str, int]]) -> int:
    tokens = _tokens(name)
    if not tokens:
        return 0
    # 编码/编号类标识列不参与语义角色匹配
    if any(t in _SKIP_TOKENS for t in tokens):
        return 0
    joined = "".join(tokens)
    bounds: set[int] = set()
    pos = 0
    for t in tokens:
        bounds.add(pos)
        pos += len(t)
    bounds.add(pos)
    score = 0
    for kw, w in keywords:
        k = _norm(kw)
        if not k:
            continue
        if any(t == k for t in tokens):
            score += w * 3
            continue
        if k in joined:
            if _is_cjk(k):
                # 中文关键词按整列包含匹配（如 客户 匹配 客户名称）
                score += w
                continue
            # 英文关键词需落在 token 边界，避免 groupcustname 误含 upcust
            i = joined.find(k)
            if i >= 0 and i in bounds and (i + len(k)) in bounds:
                score += w
                continue
        # 英文关键词是某个 token 的子串（如 qty 在 quantity 内）
        if not _is_cjk(k) and any(k in t for t in tokens):
            score += w
    return score


def detect_industry(df: pd.DataFrame) -> tuple[str, int, list[str]]:
    """返回 (行业, 置信度0-100, 命中信号)。列名 + 抽样列值双重识别。"""
    columns = list(df.columns)
    sample_text = " ".join(columns)
    for col in columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            sample_text += " " + " ".join(df[col].dropna().astype(str).head(200))
    norm_text = _norm(sample_text)
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for industry, signals in INDUSTRY_SIGNALS.items():
        s = 0
        h = []
        for sig in signals:
            if _norm(sig) in norm_text:
                s += 2
                h.append(sig)
        scores[industry] = s
        hits[industry] = h
    best = max(scores, key=lambda k: scores[k])
    confidence = min(100, scores[best] * 8 + 10)
    if scores[best] == 0:
        return "通用", 0, []
    return best, confidence, hits[best]


def map_semantics(df: pd.DataFrame) -> dict[str, Any]:
    """把 DataFrame 列自动映射为语义角色，返回 {role: column_name 或 None}。"""
    columns = list(df.columns)
    mapping: dict[str, Any] = {role: None for role in ROLE_KEYWORDS}
    used: set[str] = set()

    # 时间列优先用 dtype 兜底
    for col in columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if mapping["time"] is None:
                mapping["time"] = col
                used.add(col)
            break

    for role, keywords in ROLE_KEYWORDS.items():
        if role == "time" and mapping["time"] is not None:
            continue
        best_col, best_score = None, 0
        for col in columns:
            if col in used:
                continue
            sc = _score_column(col, keywords)
            if sc > best_score:
                best_score = sc
                best_col = col
        if best_col is not None and best_score >= 3:
            mapping[role] = best_col
            used.add(best_col)

    # 度量：金额优先于数量（两者可并存，不互斥）
    mapping["measure_amount"] = None
    mapping["measure_qty"] = None
    for role in ("measure_amount", "measure_qty"):
        best_col, best_score = None, 0
        for col in columns:
            sc = _score_column(col, ROLE_KEYWORDS[role])
            if sc > best_score:
                best_score = sc
                best_col = col
        if best_col is not None and best_score >= 3:
            mapping[role] = best_col

    industry, confidence, hits = detect_industry(df)
    mapping["_industry"] = industry
    mapping["_industry_confidence"] = confidence
    mapping["_industry_signals"] = hits
    # 数据口径：有“时效/履约”字段 → 配送口径；否则按“销售/实销/门店”字样判断为实销口径
    if mapping["delivery"] is not None:
        mapping["_flow_type"] = "配送"
    elif any(
        (str(col).lower().startswith("up_") or "upcust" in str(col).lower())
        and any(
            str(c).lower().startswith("down_") or "downcust" in str(c).lower()
            for c in columns
        )
        for col in columns
    ):
        # 存在 up_* / down_*（上游/下游客户）等流向型字段 → 配送/流向口径
        mapping["_flow_type"] = "配送/流向"
    elif any(any(k in str(col) for k in ("销售", "实销", "门店")) for col in columns):
        mapping["_flow_type"] = "实销"
    else:
        mapping["_flow_type"] = "通用"
    return mapping


def labels_for(industry: str) -> dict[str, str]:
    return INDUSTRY_LABELS.get(industry, INDUSTRY_LABELS["通用"])


def mapping_table(mapping: dict[str, Any]) -> pd.DataFrame:
    """把语义映射转成可展示的表格。"""
    rows = []
    role_names = {
        "subject": "主体", "object": "客体", "time": "时间", "space": "空间",
        "measure_amount": "度量-金额", "measure_qty": "度量-数量",
        "category": "品类/分类", "status": "状态", "delivery": "时效/履约",
    }
    for role, label in role_names.items():
        rows.append({"语义角色": label, "匹配字段": mapping.get(role) or "（未识别）"})
    return pd.DataFrame(rows)
