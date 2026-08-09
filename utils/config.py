"""统一读取配置：优先环境变量，其次 Streamlit secrets（云端）。"""

import os


def get_env(key: str, default: str = "") -> str:
    """读取配置项。本地用 .env（python-dotenv 已在 app.py 加载），云端用 secrets。"""
    value = os.getenv(key)
    if value is not None and str(value).strip() != "":
        return str(value).strip()
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None and key in secrets:
            return str(secrets[key]).strip()
    except Exception:
        pass
    return default
