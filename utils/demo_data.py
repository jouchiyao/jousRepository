"""多行业演示数据集：医药批发配送 + 零售快消。"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_DEMO_PATH = PROJECT_ROOT / "sample_data" / "real_sales_demo.csv"
REAL_STORE_DEMO_PATH = PROJECT_ROOT / "sample_data" / "real_store_demo.csv"
REAL_STORE_FULL_DEMO_PATH = PROJECT_ROOT / "sample_data" / "real_store_full_demo.csv"


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def make_pharma_demo(n: int = 5000, seed: int = 20260809) -> pd.DataFrame:
    """医药批发→门店/连锁总部配送数据（贴近用户的真实场景）。"""
    rng = _rng(seed)
    suppliers = ["华北制药", "国药控股", "华润医药", "上药集团", "九州通"]
    regions = ["华北", "华东", "华南", "西南", "华中"]
    customers = ["惠民大药房", "仁和大药房", "康泰连锁总部", "老百姓大药房", "益丰大药房", "健之佳"]
    cust_types = ["连锁总部", "零售门店", "连锁总部", "零售门店", "零售门店", "零售门店"]
    drugs = ["阿莫西林胶囊", "布洛芬缓释片", "二甲双胍片", "氯雷他定片", "奥美拉唑肠溶胶囊", "硝苯地平控释片"]
    cats = ["抗生素", "解热镇痛", "降糖药", "抗过敏", "消化系统", "心血管"]
    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 730, n), unit="D")
    qty = rng.integers(10, 2000, n)
    price = rng.choice([8.5, 15.0, 22.5, 31.0, 45.6, 58.9], n)
    amount = qty * price
    lead = np.round(np.clip(rng.normal(24, 8, n), 4, 96), 1)
    inventory = rng.integers(200, 5000, n)

    df = pd.DataFrame(
        {
            "配送日期": dates,
            "供应商": rng.choice(suppliers, n),
            "客户名称": rng.choice(customers, n),
            "客户类型": rng.choice(cust_types, n),
            "区域": rng.choice(regions, n),
            "药品名称": rng.choice(drugs, n),
            "药品分类": rng.choice(cats, n),
            "数量(盒)": qty,
            "单价(元)": price,
            "金额(元)": amount,
            "配送时效(小时)": lead,
            "期末库存(盒)": inventory,
        }
    )

    # 注入少量业务型异常：大额订单、极端时效，用于演示异常洞察
    idx = rng.choice(n, size=12, replace=False)
    df.loc[idx, "金额(元)"] = df.loc[idx, "金额(元)"] * 8
    idx2 = rng.choice(n, size=8, replace=False)
    df.loc[idx2, "配送时效(小时)"] = 168.0
    return df


def make_retail_demo(n: int = 3000, seed: int = 20260810) -> pd.DataFrame:
    """零售快消：门店 × 商品 × 日销量。"""
    rng = _rng(seed)
    stores = ["中心店", "万达店", "东门店", "西城店", "大学城店"]
    regions = ["华东", "华南", "华北"]
    goods = ["矿泉水", "可乐", "方便面", "薯片", "牛奶", "洗衣液"]
    cats = ["饮料", "食品", "日化"]
    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    qty = rng.integers(1, 200, n)
    price = rng.choice([2.0, 3.5, 5.0, 6.5, 12.0, 29.9], n)
    sales = qty * price
    stock = rng.integers(10, 800, n)
    return pd.DataFrame(
        {
            "销售日期": dates,
            "门店": rng.choice(stores, n),
            "区域": rng.choice(regions, n),
            "商品名称": rng.choice(goods, n),
            "商品分类": rng.choice(cats, n),
            "销量(件)": qty,
            "销售额(元)": sales,
            "期末库存(件)": stock,
        }
    )


def make_real_sales_demo(n: int | None = None) -> pd.DataFrame:
    """本地真实零售实销流向数据（已脱敏）。

    数据来自 scripts/build_real_demo.py 生成的 sample_data/real_sales_demo.csv；
    文件不存在时回退为模拟数据，避免应用报错。
    """
    if REAL_DEMO_PATH.exists():
        df = pd.read_csv(REAL_DEMO_PATH)
        df["业务日期"] = pd.to_datetime(df["业务日期"], errors="coerce")
        return df
    return make_pharma_demo(5000)


def make_real_store_demo(n: int | None = None) -> pd.DataFrame:
    """本地真实门店实销流向（原始导出 → 严格清洗 + 脱敏）。

    数据来自 scripts/build_real_store_demo.py 生成的 sample_data/real_store_demo.csv；
    文件不存在时回退为模拟数据，避免应用报错。
    """
    if REAL_STORE_DEMO_PATH.exists():
        df = pd.read_csv(REAL_STORE_DEMO_PATH)
        df["销售日期"] = pd.to_datetime(df["销售日期"], errors="coerce")
        return df
    return make_retail_demo(5000)


def make_real_store_full_demo(n: int | None = None) -> pd.DataFrame:
    """本地真实门店销售流向全量查询（清洗版导出，脱敏）。

    数据来自 D:\\youhou\\浏览器\\引出数据_门店销售流向全量查询_0319160546.xlsx
    （465,170 行 → 去重后 369,906 行，2024-12-26 ~ 2025-02-25）。
    文件较大（约 69MB），仅在本机存在时启用；缺失时回退到较小示例。
    """
    if REAL_STORE_FULL_DEMO_PATH.exists():
        df = pd.read_csv(REAL_STORE_FULL_DEMO_PATH)
        df["销售日期"] = pd.to_datetime(df["销售日期"], errors="coerce")
        return df
    return make_real_store_demo()


DEMOS = {
    "真实零售实销流向（脱敏·本地）": make_real_sales_demo,
    "真实门店销售流向全量（脱敏·本地）": make_real_store_full_demo,
    "真实门店实销流向（脱敏·本地）": make_real_store_demo,
    "医药批发配送（贴近真实场景）": make_pharma_demo,
    "零售快消门店销售": make_retail_demo,
}
