"""一站式智能数据分析工作台（Streamlit）。

四大支柱：描述性 → 诊断性 → 预测性 → 规范性
双引擎：MySQL / PostgreSQL 直连 + CSV / Excel 上传
访问控制：Supabase 访客计数（免费限 2 次）+ 本地降级 + 管理员无限
"""

import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

st.set_page_config(page_title="智能数据分析工作台", page_icon="📊", layout="wide")

# Streamlit 热重载只会重跑 app.py，已缓存的 utils 模块不会自动刷新；
# 强制按磁盘版本重新加载，避免长期运行的进程使用旧函数签名导致 TypeError
# （例如 time_series_analysis 缺少 freq 参数）。
import importlib as _importlib

for _m in ("utils.demo_data", "utils.semantic_mapper", "utils.analytics", "utils.report"):
    try:
        _importlib.reload(_importlib.import_module(_m))
    except Exception:  # noqa: BLE001
        pass

from utils.admin_panel import is_admin, render_admin_panel, verify_password
from utils.analytics import correlation_analysis, drilldown, run_analysis_pipeline, time_series_analysis
from utils.config import get_env
from utils.data_loader import coerce_types, load_uploaded_file
from utils.db_engine import run_query, test_connection
from utils.demo_data import DEMOS
from utils.report import _build_strategy, build_report_md
from utils.semantic_mapper import labels_for, map_semantics, mapping_table
from utils.visitor_tracker import FREE_LIMIT, VisitorTracker, get_client_info

MAX_ROWS = int(get_env("MAX_ROWS", "300000"))

FREQ_OPTIONS = {"按月": "ME", "按周": "W", "按日": "D", "按年": "YE"}

_CJK_SETUP_DONE = False


def _has_cjk_font(font_manager) -> bool:
    for name in ("Noto Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "PingFang SC", "WenQuanYi Zen Hei"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            return True
    return False


def _download_noto(font_manager) -> None:
    """内置字体缺失时的备用方案：从 CDN 下载 Noto Sans SC（OFL 开源协议）。"""
    try:
        import tempfile
        import urllib.request

        cache = os.path.join(tempfile.gettempdir(), "codex_fonts")
        os.makedirs(cache, exist_ok=True)
        dest = os.path.join(cache, "NotoSansSC-Regular.otf")
        if not os.path.exists(dest):
            urls = [
                "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
                "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
            ]
            ok = False
            for url in urls:
                try:
                    urllib.request.urlretrieve(url, dest)
                    ok = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            if not ok:
                return
        font_manager.fontManager.addfont(dest)
    except Exception:  # noqa: BLE001
        pass


def _setup_cjk_font() -> None:
    """注册系统中文字体并配置 matplotlib，避免热力图/时序图中文变乱码（豆腐块）。"""
    global _CJK_SETUP_DONE
    if _CJK_SETUP_DONE:
        return
    _CJK_SETUP_DONE = True
    try:
        import os

        from matplotlib import font_manager

        # 1) 优先注册仓库内置的 Noto Sans SC（OFL 开源协议，云端可直接使用）
        bundled = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "fonts", "NotoSansSC-Regular.otf",
        )
        if os.path.exists(bundled):
            try:
                font_manager.fontManager.addfont(bundled)
            except Exception:  # noqa: BLE001
                pass

        # 2) 注册系统常见中文字体
        candidates = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyh.ttf",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    font_manager.fontManager.addfont(p)
                except Exception:  # noqa: BLE001
                    pass

        # 3) 仍无中文字体时从 CDN 下载（备用）
        if not _has_cjk_font(font_manager):
            _download_noto(font_manager)

        import matplotlib.pyplot as plt

        plt.rcParams["font.sans-serif"] = [
            "Noto Sans SC",
            "Noto Sans CJK SC",
            "Microsoft YaHei",
            "SimHei",
            "PingFang SC",
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:  # noqa: BLE001
        pass


@st.cache_resource
def get_tracker() -> VisitorTracker:
    return VisitorTracker()


def render_corr_heatmap(corr):
    """相关性热力图（matplotlib，懒加载）。"""
    if corr is None or corr.shape[1] < 2:
        return
    if corr.shape[0] > 12:
        keep = corr.abs().mean().sort_values(ascending=False).head(12).index
        corr = corr.loc[keep, keep]
    _setup_cjk_font()
    import matplotlib.pyplot as plt

    labels = [str(c) if len(str(c)) <= 10 else str(c)[:9] + "…" for c in corr.columns]
    fig, ax = plt.subplots(figsize=(max(5.5, corr.shape[0] * 0.85), max(4.2, corr.shape[0] * 0.7)))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(corr)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_title("相关性热力图")
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")
    fig.tight_layout()
    st.pyplot(fig)


def run_analysis(df, tracker, visitor_id, count_usage: bool) -> None:
    """执行四层分析；普通访客先校验额度，成功后计数 +1。"""
    allowed, msg = True, ""
    if count_usage:
        allowed, _, msg = tracker.can_execute(visitor_id)
    if not allowed:
        st.error("⛔ 您已达到免费使用上限（2次），请联系管理员")
        st.session_state["visit_count"] = tracker.get_visit_count(visitor_id)
        return
    with st.spinner("正在执行四层分析：现象 → 归因 → 预测 → 策略…"):
        try:
            df2, _ = coerce_types(df)
            semantics = map_semantics(df2)
            results = run_analysis_pipeline(df2, semantics)
            labels = labels_for(semantics.get("_industry", "通用"))
            results["strategy"] = _build_strategy(results, labels)
            results["report_md"] = build_report_md(results)
            if count_usage:
                rec = tracker.record_execution(visitor_id)
                st.session_state["visit_count"] = int(rec.get("visit_count", 0))
            st.session_state["analysis"] = results
            st.success("✅ 分析完成" + ("（已记录 1 次使用）" if count_usage else "（管理员模式，不消耗次数）"))
        except Exception as exc:  # noqa: BLE001
            st.error(f"分析失败：{exc}")


def sidebar_data_source(tracker, visitor_id) -> None:
    st.sidebar.subheader("🗂️ 数据源")
    src = st.sidebar.radio("选择数据来源", ["数据库连接", "文件上传", "示例数据"], key="src_type")

    if src == "数据库连接":
        db_type = st.sidebar.selectbox("数据库类型", ["MySQL", "PostgreSQL"], key="db_type")
        default_port = 3306 if db_type == "MySQL" else 5432
        host = st.sidebar.text_input("主机地址", value=get_env("DB_HOST", "127.0.0.1"), key="db_host")
        port = st.sidebar.number_input("端口", min_value=1, max_value=65535, value=default_port, key="db_port")
        database = st.sidebar.text_input("数据库名", value=get_env("DB_NAME", ""), key="db_name")
        user = st.sidebar.text_input("用户名", value=get_env("DB_USER", ""), key="db_user")
        password = st.sidebar.text_input("密码", type="password", value=get_env("DB_PASSWORD", ""), key="db_pwd")
        sql = st.sidebar.text_area(
            "SQL 查询",
            value="SELECT * FROM 你的表名 LIMIT 100000",
            height=110,
            key="db_sql",
        )
        st.sidebar.caption(
            f"单次最多加载 {MAX_ROWS:,} 行；超过自动截断并提示。"
            "已兼容英文缩写列名（biz_date / prod_name / total_price 等）自动语义映射。"
            "重复单据建议在 SQL 中用 SELECT DISTINCT 或按单据号去重后再分析。"
        )
        c1, c2 = st.sidebar.columns(2)
        if c1.button("🔌 测试连接", key="btn_test"):
            ok, msg = test_connection(db_type, host, int(port), database, user, password)
            if ok:
                st.sidebar.success(msg)
            else:
                st.sidebar.error(msg)
        if c2.button("📥 加载数据", key="btn_load_db"):
            if not database or not user:
                st.sidebar.error("请填写数据库名与用户名")
            else:
                try:
                    loaded, truncated, msg = run_query(
                        db_type, host, int(port), database, user, password, sql, max_rows=MAX_ROWS
                    )
                    st.session_state["df"] = loaded
                    st.session_state["source_name"] = f"{db_type} / {database}"
                    if truncated:
                        st.sidebar.warning(msg)
                    else:
                        st.sidebar.success(msg)
                except Exception as exc:  # noqa: BLE001
                    st.sidebar.error(str(exc))

    elif src == "文件上传":
        up = st.sidebar.file_uploader("拖拽或选择 CSV / Excel", type=["csv", "txt", "xlsx", "xls"], key="up_file")
        if up is not None and st.sidebar.button("📥 载入文件", key="btn_load_file"):
            try:
                loaded = load_uploaded_file(up)
                st.session_state["df"] = loaded
                st.session_state["source_name"] = up.name
                st.sidebar.success(f"已载入 {len(loaded):,} 行 × {loaded.shape[1]} 列")
            except Exception as exc:  # noqa: BLE001
                st.sidebar.error(f"载入失败：{exc}")

    else:
        demo_name = st.sidebar.selectbox("演示数据", list(DEMOS.keys()), key="demo_name")
        is_real = demo_name.startswith("真实")
        n = st.sidebar.slider(
            "模拟数据行数（真实数据自动使用全量）",
            500, 10000, 3000, step=500, key="demo_n", disabled=is_real,
        )
        if st.sidebar.button("✨ 载入示例数据", key="btn_demo"):
            st.session_state["df"] = DEMOS[demo_name](n=n)
            st.session_state["source_name"] = demo_name
            st.sidebar.success(
                f"已载入 {len(st.session_state['df']):,} 行示例数据"
            )

    df = st.session_state.get("df")
    if df is not None:
        st.sidebar.divider()
        st.sidebar.markdown(f"**当前数据**：{st.session_state.get('source_name', '')}")
        st.sidebar.caption(f"{len(df):,} 行 × {df.shape[1]} 列")
        if st.sidebar.button("🚀 开始智能分析（普通访客消耗 1 次）", type="primary", key="btn_analyze"):
            run_analysis(df, tracker, visitor_id, count_usage=not is_admin())


def tab_overview(df, analysis) -> None:
    st.subheader("数据快照")
    if analysis:
        q = analysis["quality"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("行数", f"{q['行数']:,}")
        m2.metric("列数", q["列数"])
        m3.metric("重复行", f"{q['重复行']:,}")
        m4.metric("缺失单元格", f"{q['缺失单元格']:,}")
    st.caption("原始数据预览（前 1000 行）")
    st.dataframe(df.head(1000), use_container_width=True, hide_index=True)
    if analysis:
        st.subheader("描述性统计（含缺失率 / 极值 / 偏度峰度）")
        st.dataframe(analysis["describe"], use_container_width=True, hide_index=True)
        outliers = analysis.get("outliers") or {}
        if outliers:
            st.subheader("⚠️ 异常洞察")
            for col, det in list(outliers.items())[:6]:
                st.warning(f"「{col}」：{det['count']} 个异常（{det['method']}，合理区间 {det['bounds']}）")
                for r in det["reasons"]:
                    st.caption(f"  · {r}")


def tab_diagnostic(df, analysis) -> None:
    if not analysis:
        st.info("请先在左侧点击「开始智能分析」")
        return
    st.subheader("多维度下钻（按 主体/客体/空间/品类/时间）")
    dim_cols = [c for c in df.columns if df[c].nunique(dropna=True) < 500]
    if not dim_cols:
        st.warning("没有适合下钻的维度列（所有列的唯一值都超过 500）")
        return
    dim = st.selectbox("维度字段", dim_cols, key="dim")
    num_cols = analysis.get("numeric_cols") or []
    measure_opts = ["（计数）"] + num_cols
    measure = st.selectbox("度量字段", measure_opts, key="dim_measure")
    agg = st.selectbox("聚合方式", ["sum", "mean", "count", "max", "min"], key="dim_agg")
    value_col = None if measure == "（计数）" else measure
    dd = drilldown(df, dim, value_col, agg=agg, top_n=15)
    st.dataframe(dd, use_container_width=True, hide_index=True)
    st.bar_chart(dd.set_index(dd.columns[0])[dd.columns[1]])

    if analysis.get("pareto"):
        st.subheader("帕累托分析（二八法则）")
        p = analysis["pareto"]
        st.caption(
            f"按「{analysis.get('pareto_group')}」聚合：前 {p['k80']} 项累计贡献 {p['top80_share']:.1%}，"
            f"共 {p['n_groups']} 项"
        )
        pt = p["table"].head(20)
        st.bar_chart(pt.set_index("项")["值"])
        st.dataframe(pt, use_container_width=True, hide_index=True)

    corr = analysis.get("corr")
    if corr is not None:
        st.subheader("相关性热力图")
        render_corr_heatmap(corr)
        top3 = analysis.get("corr_top3") or []
        if top3:
            from utils.analytics import explain_correlation

            for a, b, r in top3:
                st.markdown(f"- {explain_correlation(a, b, r)}")


def tab_predictive(df, analysis) -> None:
    if not analysis:
        st.info("请先在左侧点击「开始智能分析」")
        return
    sem = analysis.get("semantics") or {}
    tcol = sem.get("time")
    mcol = sem.get("measure_amount") or sem.get("measure_qty")
    if not tcol or tcol not in df.columns or not mcol or mcol not in df.columns:
        st.warning("当前数据缺少时间字段或度量字段，无法进行时序预测。")
        return

    times = pd.to_datetime(df[tcol], errors="coerce")
    dmin, dmax = times.min(), times.max()
    if pd.isna(dmin) or pd.isna(dmax):
        st.warning("时间字段无法解析，无法进行时序预测。")
        return

    c1, c2, c3 = st.columns([1, 1, 2])
    freq_sel = c1.selectbox("时间粒度（下钻）", list(FREQ_OPTIONS.keys()), index=0, key="ts_freq")
    n_fc = int(c2.number_input("预测期数", min_value=1, max_value=6, value=3, key="ts_n"))
    if dmin.date() == dmax.date():
        start, end = dmin.date(), dmax.date()
    else:
        picked = c3.date_input(
            "日期范围（下钻）",
            value=(dmin.date(), dmax.date()),
            min_value=dmin.date(),
            max_value=dmax.date(),
            key="ts_range",
        )
        if isinstance(picked, (list, tuple)) and len(picked) == 2:
            start, end = picked
        else:
            start, end = dmin.date(), dmax.date()

    mask = (times >= pd.Timestamp(start)) & (times <= pd.Timestamp(end))
    sub = df[mask]
    if sub.empty:
        st.warning("所选日期范围内没有数据，请调整范围。")
        return

    ts = time_series_analysis(sub, tcol, mcol, forecast_n=n_fc, freq=FREQ_OPTIONS[freq_sel])
    if not ts:
        st.warning("所选粒度下有效周期不足（至少 2 期），请切换更细粒度或扩大日期范围。")
        return

    _setup_cjk_font()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(ts["series"].index, ts["series"].values, label="实际", color="#2563eb", linewidth=1.6)
    ax.plot(ts["trend"].index, ts["trend"].values, label="趋势（移动平均）", color="#f28e2b", linewidth=1.4, linestyle="--")
    fc_idx = pd.to_datetime(ts["forecast_index"])
    ax.plot(fc_idx, ts["forecast"], label="预测", color="#dc2626", marker="o", linewidth=1.6, markersize=4.5)

    series = ts["series"]
    if len(series):
        peak_idx, peak_val = series.idxmax(), float(series.max())
        ax.annotate(
            f"峰值 {peak_val:,.0f}",
            xy=(peak_idx, peak_val),
            xytext=(0, 12),
            textcoords="offset points",
            fontsize=9,
            ha="center",
            color="#dc2626",
            arrowprops={"arrowstyle": "->", "color": "#dc2626", "lw": 0.8},
        )
    # 纵轴留出余量，保证任何窗口比例下峰值都完整可见
    all_vals = list(series.values) + list(ts["forecast"])
    ymin, ymax = min(all_vals), max(all_vals)
    pad = (ymax - ymin) * 0.10 or (abs(ymax) * 0.05) or 1.0
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.grid(alpha=0.3)
    ax.legend(loc="best", framealpha=0.92, fontsize=9)
    ax.set_title(f"{mcol} 时间序列（{ts['freq_label']}）")
    fig.tight_layout()
    st.pyplot(fig)

    m1, m2, m3 = st.columns(3)
    m1.metric("模型拟合 R²", f"{ts['r2']:.2f}")
    m2.metric("趋势斜率", f"{ts['slope']:,.2f} / 期")
    m3.metric("下一期预测", f"{ts['forecast'][0]:,.0f}")
    st.caption(f"模型：{ts['model']} ｜ 周期数：{ts['n']}")

    fc = pd.DataFrame(
        {
            "期数": [f"第{i + 1}期" for i in range(len(ts["forecast"]))],
            "预测时间": ts["forecast_index"],
            "预测值": ts["forecast"],
        }
    )
    st.dataframe(fc, use_container_width=True, hide_index=True)


def tab_prescriptive(analysis) -> None:
    if not analysis:
        st.info("请先在左侧点击「开始智能分析」")
        return
    st.subheader("库存周转 / 动销分析")
    to = analysis.get("turnover")
    if to:
        st.caption(to.get("method", ""))
        if to.get("days") is not None and len(to["days"]):
            st.line_chart(to["days"].rename("周转天数"))
        elif to.get("turnover") is not None:
            st.line_chart(to["turnover"].rename("动销强度"))
    st.subheader("💡 规范化建议（可执行）")
    for tip in analysis.get("strategy", []):
        st.success(tip)


def tab_semantics(analysis) -> None:
    if not analysis:
        st.info("请先在左侧点击「开始智能分析」")
        return
    sem = analysis["semantics"]
    industry = sem.get("_industry", "通用")
    flow = sem.get("_flow_type", "通用")
    st.info(
        f"识别行业：**{industry}**（置信度 {sem.get('_industry_confidence', 0)}%）"
        f"　·　数据口径：**{flow}**"
        f"　·　命中信号：{'、'.join(sem.get('_industry_signals', [])[:8]) or '无'}"
    )
    st.dataframe(mapping_table(sem), use_container_width=True, hide_index=True)
    st.caption(
        "语义层把任意行业字段统一抽象为 主体/客体/时间/度量/空间，"
        "因此同一套分析逻辑可用于医药、零售、快消、物流等不同数据。"
    )


def tab_report(analysis) -> None:
    if not analysis:
        st.info("请先在左侧点击「开始智能分析」")
        return
    st.download_button(
        "⬇ 下载 Markdown 报告",
        analysis["report_md"].encode("utf-8"),
        "数据分析报告.md",
        "text/markdown",
        key="btn_download_report",
    )
    st.markdown(analysis["report_md"])


def main() -> None:
    tracker = get_tracker()
    visitor_id, _, _ = get_client_info()
    st.session_state.setdefault("visitor_id", visitor_id)
    st.session_state.setdefault("admin_ok", False)
    if "visit_count" not in st.session_state:
        st.session_state["visit_count"] = tracker.get_visit_count(visitor_id)

    with st.sidebar:
        st.title("⚙️ 控制台")
        if is_admin():
            st.success("👑 管理员模式：使用次数不受限制")
        else:
            remaining = max(0, FREE_LIMIT - int(st.session_state["visit_count"]))
            st.info(f"访客剩余次数：**{remaining}/2**（按 IP + 浏览器标识识别）")
        if tracker.mode == "local":
            st.warning(
                "⚠️ Supabase 未配置或不可用，已降级为本地存储计数，限制可能不跨设备/实例。"
            )
        if tracker.last_error:
            st.caption(f"存储提示：{tracker.last_error}")
        pw = st.text_input("管理员密码", type="password", key="admin_pw")
        if st.button("验证管理员", key="btn_admin"):
            if verify_password(pw):
                st.session_state["admin_ok"] = True
                st.success("✅ 已进入管理员模式")
            else:
                st.session_state["admin_ok"] = False
                st.error("❌ 密码错误")
        if is_admin():
            with st.expander("🔒 访客访问记录（管理）"):
                render_admin_panel(tracker)
        st.divider()

    sidebar_data_source(tracker, visitor_id)

    st.title("📊 一站式智能数据分析工作台")
    st.caption(
        "四层方法论：描述性 → 诊断性 → 预测性 → 规范性 ｜ 双引擎：MySQL / PostgreSQL + CSV / Excel ｜ "
        "多行业：医药 / 零售 / 快消 / 物流（字段自动语义映射）"
    )

    df = st.session_state.get("df")
    if df is None:
        st.info("👈 请从左侧控制台选择数据源并加载数据，或点击「示例数据」快速体验。")
        return

    analysis = st.session_state.get("analysis")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📋 数据概览", "🔍 诊断分析", "🔮 预测分析", "💡 策略建议", "🧩 语义映射", "📄 完整报告"]
    )
    with tab1:
        tab_overview(df, analysis)
    with tab2:
        tab_diagnostic(df, analysis)
    with tab3:
        tab_predictive(df, analysis)
    with tab4:
        tab_prescriptive(analysis)
    with tab5:
        tab_semantics(analysis)
    with tab6:
        tab_report(analysis)


if __name__ == "__main__":
    main()
