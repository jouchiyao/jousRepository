# 📊 一站式智能数据分析工作台

基于 **Streamlit + Pandas + NumPy** 构建的多行业数据分析应用：从数据接入、字段语义映射，
到「描述 → 诊断 → 预测 → 策略」四层递进分析，内置零售快消门店销售演示数据，开箱即用。

## ✨ 项目亮点

- **字段语义层**：自动把任意数据映射为 主体 / 客体 / 时间 / 度量 / 空间，兼容中文与英文缩写列名
  （`biz_date / prod_name / total_price` 等），同一套逻辑适配医药、零售、快消、物流数据
- **经营 KPI**：累计销售额、毛利率、客单价、会员订单占比、月度环比/同比、促销表现
- **ABC × XYZ 库存矩阵**：销售额贡献分层（A/B/C）× 需求波动分层（X/Y/Z），输出差异化库存策略
- **促销归因**：按品类量化促销带来的销量提升，识别高弹性品类
- **时序预测 + 样本外回测**：月度/周度/日度粒度可切换，线性回归 + 季节调整，留出样本验证
  MAPE，并与朴素基线对比
- **异常洞察**：IQR / 3-Sigma 离群检测 + 异常聚集维度定位
- **相关性挖掘**：热力图 + Top3 相关关系文字解读
- **四层报告**：现象 → 归因 → 预测 → 策略，一键导出 Markdown
- **访问控制**：普通访客限次、管理员密码解锁、访客记录面板（Supabase 可选）

## 🧪 内置演示数据

**零售快消门店销售（18 个月）**：

- 时间跨度：2024-01-01 ~ 2025-06-30
- 规模：约 10.8 万行，8 家门店 × 4 大区域 × 25 个 SKU × 5 个品类
- 字段：日期、门店、区域、商品名称、商品分类、销量、销售额、成本、毛利、单价、
  订单数、会员订单数、期末库存、是否促销
- 数据特征：季节性（夏季饮料/乳品旺销、春节粮油礼盒）、周末效应、促销提量、
  部分 SKU 高需求波动（爆款/缺货）、整体温和增长趋势

## 🚀 快速开始

```bash
pip install -r requirements.txt
streamlit run app.py
```

打开 `http://localhost:8501`，侧边栏选择「示例数据」→ 载入 → 「开始智能分析」。

## 🗂 目录结构

```
data-workbench/
├── app.py                  # Streamlit 主程序
├── requirements.txt
├── .env.example
├── assets/fonts/           # Noto Sans SC（OFL 开源字体，保证云端图表中文正常）
└── utils/
    ├── analytics.py        # KPI / ABC-XYZ / 促销归因 / 时序回测 / 异常 / 相关
    ├── semantic_mapper.py  # 通用语义层映射 + 行业与数据口径识别
    ├── report.py           # 四层报告生成
    ├── demo_data.py        # 零售快消示例数据生成
    ├── data_loader.py      # CSV / Excel 导入与类型推断
    ├── db_engine.py        # MySQL / PostgreSQL 连接与查询
    ├── visitor_tracker.py  # 访客计数（Supabase / 本地降级）
    ├── admin_panel.py      # 管理员访客记录面板
    └── config.py
```

## ☁️ 部署到 Streamlit Community Cloud

1. 推送代码到 GitHub 仓库（分支 `main`）；
2. 打开 [share.streamlit.io](https://share.streamlit.io) → New app → 选择仓库、
   `main` 分支、`app.py` → Deploy；
3. （可选）Settings → Secrets 配置：

```toml
ADMIN_PASSWORD = "你的管理员密码"
MAX_ROWS = "300000"
```

> 说明：`supabase-py` 目前无 Python 3.13/3.14 版本，共享版默认不安装，访客计数自动降级为
> 本地存储；如需启用 Supabase 访客计数，请在 Advanced settings 选择 Python 3.12，
> 并把 `supabase-py>=2.4,<3` 加回 `requirements.txt`。

## 🧠 分析方法论

| 支柱 | 内容 |
| --- | --- |
| 描述性 | 数据质量、缺失率、极值、分布形态（偏度/峰度）、经营 KPI |
| 诊断性 | 多维度下钻、帕累托/ABC 分层、XYZ 波动分类、促销归因、相关性 Top3、异常聚集定位 |
| 预测性 | 时序分解（趋势+季节）、未来 3 期预测、样本外回测 MAPE 对比朴素基线 |
| 规范性 | ABC-XYZ 库存策略、促销预算配置、会员运营、补货与数据质量规则 |

## 🛠 技术栈

Streamlit · Pandas · NumPy · Matplotlib · SQLAlchemy · PyMySQL · python-dotenv
