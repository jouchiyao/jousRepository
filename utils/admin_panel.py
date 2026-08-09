"""管理员面板：查看所有访客访问记录，支持导出 CSV。"""

from __future__ import annotations

import streamlit as st

from utils.config import get_env


def verify_password(pw: str) -> bool:
    expected = get_env("ADMIN_PASSWORD")
    return bool(expected) and pw == expected


def is_admin() -> bool:
    return bool(st.session_state.get("admin_ok", False))


def render_admin_panel(tracker) -> None:
    """隐藏页面：通过管理员密码进入，展示访客记录并支持导出。"""
    st.subheader("🔒 访客访问记录")
    st.caption("表结构：id / visitor_id / visit_count / first_visit / last_visit（Supabase 或本地降级）")
    try:
        df = tracker.list_visitors()
        st.dataframe(df, use_container_width=True, hide_index=True)
        if len(df):
            total = int(df["visit_count"].sum())
            st.caption(f"访客总数：{len(df)}　|　累计分析执行次数：{total}")
            st.download_button(
                "⬇ 导出 CSV",
                df.to_csv(index=False).encode("utf-8-sig"),
                "visitor_records.csv",
                "text/csv",
                key="btn_export_visitors",
            )
        else:
            st.info("暂无访问记录")
    except Exception as exc:  # noqa: BLE001
        st.error(f"读取访客记录失败：{exc}")
