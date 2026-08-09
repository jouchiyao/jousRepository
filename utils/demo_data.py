"""内置演示数据：零售快消门店销售（18 个月，含促销/毛利/会员/库存维度）。

用于简历/作品集展示的干净示例：字段语义清晰，可完整支撑 KPI、ABC-XYZ、
促销归因、时序预测等分析。
"""

import numpy as np
import pandas as pd


def make_retail_demo(n: int | None = None, seed: int = 20260810) -> pd.DataFrame:
    """生成 2024-01-01 ~ 2025-06-30 的零售门店日销售数据。

    n 提供时从全量数据中随机抽样（用于快速演示）；默认返回全量约 8 万行。
    """
    rng = np.random.default_rng(seed)
    stores = [
        ("上海徐汇店", "华东"), ("上海浦东店", "华东"), ("杭州西湖店", "华东"), ("南京新街口店", "华东"),
        ("广州天河店", "华南"), ("深圳福田店", "华南"), ("北京朝阳店", "华北"), ("成都锦江店", "西南"),
    ]
    skus = {
        "饮料": [
            ("冰红茶500ml", 3.5, 1.8), ("矿泉水550ml", 2.0, 0.7), ("可乐330ml", 3.0, 1.2),
            ("鲜榨果汁300ml", 6.5, 3.2), ("气泡水480ml", 4.5, 2.1),
        ],
        "食品": [
            ("薯片原味", 6.0, 2.8), ("巧克力排块", 12.0, 6.0), ("苏打饼干", 5.5, 2.6),
            ("每日坚果25g", 9.9, 4.8), ("辣条100g", 4.5, 2.0),
        ],
        "乳品": [
            ("纯牛奶250ml", 3.2, 1.9), ("低温酸奶100g", 4.5, 2.6), ("芝士奶酪片", 15.0, 8.5),
            ("豆奶300ml", 3.8, 2.0), ("常温酸奶200g", 6.0, 3.3),
        ],
        "日化": [
            ("洗衣液2kg", 29.9, 15.0), ("洗发水750ml", 39.9, 21.0), ("牙膏120g", 12.9, 5.8),
            ("卷纸10卷", 16.9, 8.2), ("沐浴露650ml", 24.9, 13.0),
        ],
        "粮油": [
            ("东北大米5kg", 39.9, 28.0), ("花生油5L", 89.9, 62.0), ("生抽500ml", 9.9, 5.2),
            ("挂面1kg", 8.5, 4.6), ("方便面五连包", 12.5, 7.0),
        ],
    }
    popularity = {
        name: int(rng.integers(4, 28))
        for cat, items in skus.items()
        for name, *_ in items
    }
    # 部分 SKU 需求波动更大（爆款/缺货），用于 XYZ 分层与异常场景
    volatility = {
        "鲜榨果汁300ml": 0.55,
        "辣条100g": 0.5,
        "每日坚果25g": 0.45,
        "气泡水480ml": 0.35,
    }
    # 月度需求冲击（lognormal，σ 越大月度波动越强），用于 XYZ 需求波动分层
    monthly_vol = {
        "鲜榨果汁300ml": 0.95,
        "辣条100g": 0.70,
        "每日坚果25g": 0.55,
        "气泡水480ml": 0.35,
        "可乐330ml": 0.22,
        "薯片原味": 0.18,
    }
    dates = pd.date_range("2024-01-01", "2025-06-30", freq="D")
    shocks = {}
    for sku in popularity:
        vol = monthly_vol.get(sku, 0.06)
        for ym in dates.to_period("M").unique():
            shocks[(ym.year, ym.month, sku)] = float(rng.lognormal(0.0, vol))
    rows = []
    for date in dates:
        weekend = 1.28 if date.dayofweek >= 5 else 1.0
        summer = 1.35 if date.month in (6, 7, 8) else 1.0
        spring = 1.35 if (date.month == 1 and date.day >= 25) or (date.month == 2 and date.day <= 10) else 1.0
        trend = 1.0 + (date - dates[0]).days / 365 * 0.10
        for store, region in stores:
            for cat, items in skus.items():
                for name, price, cost in items:
                    promo = rng.random() < 0.14
                    mult = 1.0
                    if promo:
                        price = round(price * rng.uniform(0.78, 0.92), 2)
                        mult = rng.uniform(1.35, 2.15)
                    base = popularity[name] * weekend * trend
                    if cat in ("饮料", "乳品") and date.month in (6, 7, 8):
                        base *= summer
                    if cat == "粮油" and spring > 1:
                        base *= spring
                    base *= shocks[(date.year, date.month, name)]
                    vol = volatility.get(name, 0.1)
                    noise = 1.0 + rng.normal(0.0, vol)
                    if rng.random() < 0.05:
                        noise *= rng.uniform(3.0, 6.0)  # 爆款日
                    elif rng.random() < 0.03:
                        noise *= rng.uniform(0.05, 0.2)  # 缺货/断供日
                    qty = int(rng.poisson(base * mult * max(noise, 0.05)))
                    if qty <= 0:
                        continue
                    amount = round(qty * price, 2)
                    cost_amt = round(qty * cost, 2)
                    orders = max(1, int(qty / rng.uniform(1.6, 3.0)))
                    member_orders = int(orders * rng.uniform(0.45, 0.70))
                    inventory = max(int(base * rng.uniform(4.0, 9.0)), 30)
                    rows.append(
                        (
                            date.date(), store, region, name, cat, qty, amount, cost_amt,
                            amount - cost_amt, price, orders, member_orders, inventory,
                            1 if promo else 0,
                        )
                    )
    df = pd.DataFrame(
        rows,
        columns=[
            "日期", "门店", "区域", "商品名称", "商品分类", "销量(件)", "销售额(元)",
            "成本(元)", "毛利(元)", "单价(元)", "订单数(单)", "会员订单数(单)",
            "期末库存(件)", "是否促销",
        ],
    )
    if n is not None and 0 < n < len(df):
        df = df.sample(n, random_state=seed).sort_values("日期").reset_index(drop=True)
    return df


DEMOS = {
    "零售快消门店销售（18个月示例）": make_retail_demo,
}
