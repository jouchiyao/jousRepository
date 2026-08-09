"""文件导入：CSV / Excel，自动推断字段类型。"""

import io

import pandas as pd


def load_uploaded_file(uploaded_file, sheet_name=0) -> pd.DataFrame:
    """读取 Streamlit 上传的文件，返回 DataFrame。"""
    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.getvalue()
    if name.endswith((".csv", ".txt")):
        try:
            return pd.read_csv(io.BytesIO(raw))
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(raw), encoding="gbk")
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name)
    raise ValueError("不支持的格式，请上传 CSV / TXT / Excel")


def coerce_types(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """尽力推断每列类型（文本→日期/数值），返回 (新df, 类型报告)。"""
    df = df.copy()
    report = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            report[col] = "数值"
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            report[col] = "时间"
            continue
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            sample = df[col].dropna().astype(str).head(20)
            if sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").all():
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    report[col] = "时间"
                    continue
                except Exception:
                    pass
            numeric = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
            )
            if numeric.notna().mean() >= 0.9:
                df[col] = numeric
                report[col] = "数值"
                continue
        report[col] = "文本"
    return df, report
