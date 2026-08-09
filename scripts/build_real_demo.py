"""从本机真实导出数据构建脱敏演示数据集。

输入：Downloads 中的“零售销售流向全量查询”导出文件（连锁总部口径）
处理：仅保留业务字段；真实客户/门店/供应商名称 → 不可逆哈希编号；删除姓名、工号、地址等敏感列。
输出：sample_data/real_sales_demo.csv（可直接作为工作台示例数据，可随仓库发布）
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

SOURCE = Path(
    r"C:\Users\你喜欢吃药吗\Downloads\引出数据_零售销售流向全量查询连锁总部_0704141801.xlsx"
)
OUT = Path(__file__).resolve().parents[1] / "sample_data" / "real_sales_demo.csv"


def mask_name(series: pd.Series, prefix: str, salt: str) -> pd.Series:
    """真实名称 → 确定性匿名编号（同一名称始终映射到同一编号，保留分析关系）。"""
    mapping: dict[str, str] = {}
    out = []
    for v in series:
        key = str(v).strip() if pd.notna(v) else ""
        if not key:
            out.append("")
            continue
        if key not in mapping:
            h = int(hashlib.sha256((salt + key).encode("utf-8")).hexdigest()[:8], 16)
            mapping[key] = f"{prefix}{h:08d}"
        out.append(mapping[key])
    return pd.Series(out, index=series.index)


def parse_expiry_series(series: pd.Series) -> pd.Series:
    """把 20270331 / 2027-03-31 / 空 统一为 yyyy-mm-dd。"""
    t = series.astype(str).str.strip()
    t = t.mask(t.str.lower().isin(["nan", "nat", "none", ""]), "")
    mask8 = t.str.isdigit() & (t.str.len() == 8)
    t.loc[mask8] = t.loc[mask8].str.replace(r"^(\d{4})(\d{2})(\d{2})$", r"\1-\2-\3", regex=True)
    dt = pd.to_datetime(t.replace("", pd.NaT), errors="coerce")
    return dt.dt.strftime("%Y-%m-%d").fillna("")


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"未找到源文件：{SOURCE}")
    df = pd.read_excel(SOURCE, sheet_name=0)
    keep = [
        "业务日期", "客户性质.名称",
        "上游客户名称.客户名称", "标准下游客户名称.省份", "标准下游客户名称.城市",
        "标准下游客户名称.客户名称", "标准商品名称.通用名称", "标准商品名称.规格",
        "标准数量", "单价", "金额", "有效期", "生产厂家",
    ]
    df = df[[c for c in keep if c in df.columns]]
    df = df.rename(
        columns={
            "客户性质.名称": "客户类型",
            "上游客户名称.客户名称": "供应商_原值",
            "标准下游客户名称.省份": "省份",
            "标准下游客户名称.城市": "城市",
            "标准下游客户名称.客户名称": "门店_原值",
            "标准商品名称.通用名称": "商品名称",
            "标准商品名称.规格": "规格",
            "标准数量": "数量(盒)",
            "单价": "单价(元)",
            "金额": "金额(元)",
        }
    )
    # 脱敏：名称 → 匿名编号
    df["供应商"] = mask_name(df.pop("供应商_原值"), "供应商", "sup-2026")
    df["门店"] = mask_name(df.pop("门店_原值"), "门店", "store-2026")

    df["业务日期"] = pd.to_datetime(df["业务日期"], errors="coerce")
    df = df.dropna(subset=["业务日期"])
    df["年"] = df["业务日期"].dt.year
    df["月"] = df["业务日期"].dt.month
    df["有效期"] = parse_expiry_series(df["有效期"])
    df["单价(元)"] = pd.to_numeric(df["单价(元)"], errors="coerce").round(2)
    df["金额(元)"] = pd.to_numeric(df["金额(元)"], errors="coerce").round(2)
    df["数量(盒)"] = pd.to_numeric(df["数量(盒)"], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("业务日期").reset_index(drop=True)

    cols = [
        "业务日期", "年", "月", "省份", "城市", "客户类型", "供应商", "门店",
        "商品名称", "规格", "生产厂家", "数量(盒)", "单价(元)", "金额(元)", "有效期",
    ]
    df = df[[c for c in cols if c in df.columns]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"已写出脱敏数据：{OUT}")
    print(f"行数：{len(df):,}　列数：{df.shape[1]}　日期范围：{df['业务日期'].min().date()} ~ {df['业务日期'].max().date()}")
    print("列：", ", ".join(df.columns))
    print("\n前 3 行预览：")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
