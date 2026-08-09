"""数据库接入：MySQL / PostgreSQL 连接测试与查询。"""

from decimal import Decimal
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text


def build_url(db_type: str, host: str, port: int, database: str, user: str, password: str) -> str:
    user_q = quote_plus(user)
    pwd_q = quote_plus(password)
    if db_type == "MySQL":
        return f"mysql+pymysql://{user_q}:{pwd_q}@{host}:{port}/{database}?charset=utf8mb4"
    return f"postgresql+psycopg2://{user_q}:{pwd_q}@{host}:{port}/{database}"


def _make_engine(db_type: str, host: str, port: int, database: str, user: str, password: str):
    url = build_url(db_type, host, port, database, user, password)
    if db_type == "MySQL":
        return create_engine(url, connect_args={"connect_timeout": 8}, pool_pre_ping=True)
    return create_engine(url, connect_args={"connect_timeout": 8}, pool_pre_ping=True)


def test_connection(db_type: str, host: str, port: int, database: str, user: str, password: str):
    """测试数据库连通性，返回 (是否成功, 提示信息)。"""
    engine = None
    try:
        engine = _make_engine(db_type, host, port, database, user, password)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "连接成功 ✔"
    except Exception as exc:  # noqa: BLE001
        return False, f"连接失败：{exc}"
    finally:
        if engine is not None:
            engine.dispose()


def run_query(
    db_type: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    sql: str,
    max_rows: int = 300000,
) -> tuple[pd.DataFrame, bool, str]:
    """执行 SQL 并返回 DataFrame；超过 max_rows 自动截断并返回截断标记。

    返回 (df, truncated, message)。
    """
    engine = None
    try:
        engine = _make_engine(db_type, host, port, database, user, password)
        df = pd.read_sql(sql, engine)
        # MySQL DECIMAL 列会以 Decimal 对象返回，转成 float 以便统计/相关/异常检测识别
        for col in df.columns:
            if df[col].dtype == object:
                sample = df[col].dropna().head(50)
                if len(sample) and all(isinstance(x, Decimal) for x in sample):
                    df[col] = pd.to_numeric(df[col], errors="coerce")
        truncated = len(df) > max_rows
        if truncated:
            msg = (
                f"查询结果 {len(df):,} 行超过单次上限 {max_rows:,}，已截断为前 {max_rows:,} 行。"
                "建议在 SQL 中先用 GROUP BY 聚合（日期/区域/品类），1700 万行明细应推送聚合到数据库执行。"
            )
            df = df.head(max_rows).copy()
        else:
            msg = f"成功加载 {len(df):,} 行 × {df.shape[1]} 列"
        return df, truncated, msg
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"查询失败：{exc}") from exc
    finally:
        if engine is not None:
            engine.dispose()
