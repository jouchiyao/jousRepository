"""从「原始门店销售流向」多期导出构建脱敏示例数据（严格清洗版）。

输入：2025-05/06 三个连续导出（0514 / 0515 / 0611），覆盖 2025-03-26 ~ 2025-06-10。
注意：源文件是未经清洗的原始导出，本脚本执行严格清洗：
  1) 仅取「列表数据」工作表，剔除透视表残留；
  2) 统一列结构、丢弃全空列与敏感列（地址/创建修改时间/人员字段等）；
  3) 按单据编号去重 + 业务键去重（多期导出存在重叠窗口）；
  4) 日期解析、金额=数量×单价 校验、负值/缺失处理并输出质量报告；
  5) 门店/连锁总部真实名称 → 不可逆哈希编号（跨文件一致）。
输出：sample_data/real_store_demo.csv（可随仓库发布）
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

BASE = Path(
    r"C:\Users\你喜欢吃药吗\Documents\WeChat Files\wxid_yhv85k0c5wkc22\FileStorage\File"
)
SOURCES = [
    BASE / "2025-05" / "引出列表_原始门店销售流向_0514114950.xlsx",
    BASE / "2025-05" / "引出列表_原始门店销售流向_0515103818.xlsx",
    BASE / "2025-06" / "引出列表_原始门店销售流向_0611171023.xlsx",
]
OUT = Path(__file__).resolve().parents[1] / "sample_data" / "real_store_demo.csv"


def mask_name(series: pd.Series, prefix: str, salt: str) -> pd.Series:
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


def read_main_sheet(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = "列表数据" if "列表数据" in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    xl.close()
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    return df


def main() -> None:
    frames = []
    for p in SOURCES:
        if not p.exists():
            print(f"警告：跳过不存在的文件 {p}")
            continue
        df = read_main_sheet(p)
        print(f"读取 {p.name}: {len(df):,} 行 × {df.shape[1]} 列")
        frames.append(df)
    if not frames:
        raise FileNotFoundError("没有可用的源文件")

    raw = pd.concat(frames, ignore_index=True)
    raw["销售日期"] = pd.to_datetime(raw["销售日期"], errors="coerce")
    print(f"合并后: {len(raw):,} 行；日期范围 {raw['销售日期'].min()} ~ {raw['销售日期'].max()}")

    # 1) 单据级去重（多期导出存在重叠窗口）
    before = len(raw)
    raw = raw.drop_duplicates(subset=["单据编号"], keep="first")
    print(f"按单据编号去重: {before:,} → {len(raw):,}（删除 {before - len(raw):,}）")

    # 2) 业务键去重（同一笔销售的重复记录）
    key = ["销售日期", "销售单号", "原始门店编码", "商品编码", "数量", "金额"]
    before = len(raw)
    raw = raw.drop_duplicates(subset=key, keep="first")
    print(f"按业务键去重: {before:,} → {len(raw):,}（删除 {before - len(raw):,}）")

    # 3) 质量校验：金额 = 数量 × 单价
    qty = pd.to_numeric(raw["数量"], errors="coerce")
    price = pd.to_numeric(raw["单价"], errors="coerce")
    amt = pd.to_numeric(raw["金额"], errors="coerce")
    expect = qty * price
    mismatch = (amt - expect).abs() > 0.02
    print(f"金额≠数量×单价 的行: {int(mismatch.sum()):,}（{mismatch.mean():.2%}）")
    raw = raw.loc[~(mismatch & amt.notna())].copy()
    qty = qty.loc[raw.index]
    price = price.loc[raw.index]
    amt = amt.loc[raw.index]
    raw = raw.dropna(subset=["销售日期", "数量", "金额"])
    qty = qty.loc[raw.index]
    price = price.loc[raw.index]
    amt = amt.loc[raw.index]
    print(f"剔除无效行后: {len(raw):,}")
    print(f"负数量（退货/冲销）: {int((qty < 0).sum()):,}；负金额: {int((amt < 0).sum()):,}")
    print(f"单位取值: {raw['单位'].dropna().unique()[:10]}")

    # 4) 保留字段 + 脱敏
    out = pd.DataFrame(
        {
            "销售日期": raw["销售日期"],
            "年": raw["销售日期"].dt.year.astype(int),
            "月": raw["销售日期"].dt.month.astype(int),
            "区域": mask_name(raw["省公司"], "区域", "region-2026"),
            "城市": raw["城市"],
            "连锁总部": mask_name(raw["连锁总部名称"], "连锁总部", "chain-2026"),
            "门店": mask_name(raw["原始门店名称"], "门店", "store-2026"),
            "商品名称": raw["品名"],
            "通用名": raw["通用名"],
            "规格": raw["规格"],
            "生产企业": raw["生产企业"],
            "数量": qty,
            "单位": raw["单位"],
            "单价(元)": price.round(2),
            "金额(元)": amt.round(2),
            "有效期": pd.to_datetime(raw["有效期"], errors="coerce").dt.strftime("%Y-%m-%d"),
        }
    )
    out = out.sort_values(["销售日期", "门店"]).reset_index(drop=True)
    out["金额(元)"] = out["金额(元)"].fillna(out["数量"] * out["单价(元)"]).round(2)
    out = out[out["金额(元)"].notna() & (out["数量"] != 0)].reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\n已写出脱敏数据：{OUT}")
    print(f"行数：{len(out):,}　列数：{out.shape[1]}　日期范围：{out['销售日期'].min().date()} ~ {out['销售日期'].max().date()}")
    print("列：", ", ".join(out.columns))
    print("\n前 3 行预览：")
    print(out.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
