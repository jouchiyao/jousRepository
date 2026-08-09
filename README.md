# 📊 一站式智能数据分析工作台

面向**多行业（医药 / 零售 / 快消 / 物流）**数据的一站式 Streamlit 分析应用：
双引擎接入（MySQL / PostgreSQL 直连 + CSV / Excel 上传）、免注册访问控制（Supabase 计数）、
以及「现象 → 归因 → 预测 → 策略」四层递进的深度分析报告。

> **开箱即用**：仓库内置多份脱敏示例数据（零售销售流向、门店实销流向等），
> 部署后无需配置任何数据库即可体验全部功能；数据库连接为可选能力，仅供本地自连使用。

---

## 一、功能总览

| 模块 | 能力 |
| --- | --- |
| 数据接入 | MySQL / PostgreSQL 连接 UI（测试连通性）、CSV / Excel 拖拽上传、内置多行业示例数据 + 本地真实实销数据（已脱敏） |
| 访问控制 | 访客 = IP + User-Agent 哈希；普通访客永久限 **2 次**；管理员密码解锁不限次数 |
| 访问记录 | Supabase 表 `visitors`（id / visitor_id / visit_count / first_visit / last_visit），管理员隐藏页 + 导出 CSV |
| 描述性分析 | 概览、缺失率、极值、偏度/峰度、数据类型识别 |
| 诊断性分析 | 多维度下钻（主体/客体/空间/品类/时间）、帕累托二八法则、相关性热力图 + Top3 解释 |
| 预测性分析 | 简易 STL 分解（移动平均趋势 + 季节项）+ 线性回归，默认按月预测，支持日/周/月/年粒度与日期范围下钻 |
| 规范性建议 | 帕累托聚焦策略、库存周转模型、数据质量校验规则、行业专属建议 |
| 行业兼容 | 字段自动映射为通用语义层：主体 / 客体 / 时间 / 度量 / 空间，自动识别行业并切换业务叫法 |

---

## 二、目录结构

```
data-workbench/
├── app.py                     # Streamlit 主程序
├── requirements.txt           # 依赖
├── .env.example               # 环境变量模板（复制为 .env 使用）
├── .gitignore
├── README.md
└── utils/
    ├── __init__.py
    ├── config.py              # 环境变量 / Streamlit secrets 统一读取
    ├── visitor_tracker.py     # 访问计数与 Supabase 交互（含本地降级）
    ├── admin_panel.py         # 管理员查看访客记录页面
    ├── db_engine.py           # MySQL / PostgreSQL 连接与查询
    ├── data_loader.py         # CSV / Excel 上传与类型推断
    ├── semantic_mapper.py     # 通用语义层映射 + 行业识别
    ├── analytics.py           # 四层分析引擎（描述/诊断/预测/规范 + 异常 + 相关）
    ├── report.py              # 四层递进报告生成
    └── demo_data.py           # 医药批发配送 / 零售快消示例数据
├── scripts/
│   ├── build_real_demo.py     # 零售销售流向（连锁总部口径）→ 脱敏示例数据
│   └── build_real_store_demo.py  # 门店销售流向（多期原始导出）→ 清洗+脱敏示例数据
└── sample_data/
    ├── real_sales_demo.csv    # 真实零售销售流向（连锁总部口径，脱敏，73,498 行）
    └── real_store_demo.csv    # 真实门店实销流向（多期导出清洗+脱敏，27,759 行）
    └── real_store_full_demo.csv  # 真实门店销售流向全量查询（脱敏，369,906 行，约 69MB）
```

## 三、示例数据说明（脱敏）

内置两个真实数据（均已脱敏，可随仓库发布）：

1. **真实零售实销流向**：来自 `引出数据_零售销售流向全量查询连锁总部_0704141801.xlsx`
   （73,498 行，2025-05-26 ~ 06-25）。生成脚本 `scripts/build_real_demo.py` 只保留业务字段，
   并将真实「供应商 / 门店」名称替换为不可逆哈希编号。
2. **真实门店实销流向**：整合三份连续导出的原始门店销售流向
   （`引出列表_原始门店销售流向_0514/0515/0611`，覆盖 2025-03-26 ~ 06-10，34,834 行合并后去重）。
   原始导出为未经清洗数据，脚本 `scripts/build_real_store_demo.py` 执行严格清洗：
   仅取「列表数据」工作表、按单据编号与业务键去重、金额=数量×单价校验
   （剔除 17.63% 不满足勾稽的行）、保留退货/冲销负值、门店/连锁总部/区域名称匿名化，
   最终输出 27,759 行。
3. **真实门店销售流向全量**：来自 `D:\youhou\浏览器\引出数据_门店销售流向全量查询_0319160546.xlsx`
   （清洗版全量导出，465,170 行 → 去重后 369,906 行，2024-12-26 ~ 2025-02-25）。
   质量检查：金额=数量×单价勾稽 0 处不一致、关键字段近零缺失、2,993 家门店、49 个商品；
   门店/连锁总部/区域名称已匿名化。文件约 69MB，仅在本机存在时作为示例提供；
   若需发布到 GitHub/Streamlit Cloud，建议改用数据库查询或抽样后部署。

如需更新数据：修改脚本中的源文件路径后运行对应脚本即可。
> 说明：D 盘 `浏览器` 目录下还存在上百个「门店销售流向全量查询」大文件（单文件最大 150MB+），
> 扫描效率低，未纳入示例数据；如需分析这些全量数据，建议直接从数据库按日期范围查询。

---

## 四、本地运行

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 然后编辑 .env 填入真实配置
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

> 提示：本机 MySQL（127.0.0.1）**只能在本机运行 Streamlit 时直连**；部署到云端后需改用
> 公网可达的数据库（见第六节）。

---

## 五、环境变量（.env）

```dotenv
ADMIN_PASSWORD=你的管理员密码
SUPABASE_URL=https://你的项目.supabase.co
SUPABASE_KEY=你的 anon 或 service_role key
VISITOR_FALLBACK_FILE=data/visitors.json
MAX_ROWS=300000
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=你的数据库名
DB_USER=你的只读用户名
DB_PASSWORD=你的数据库密码
```

`.env` 已被 `.gitignore` 忽略，**不要提交到 GitHub**。

---

## 六、免费注册 Supabase 并获取密钥（约 5 分钟）

1. 打开 [supabase.com](https://supabase.com) → Sign Up（可用 GitHub 账号登录）。
2. 创建项目：New project → 填名称、选区域（建议选离你近的，如 Singapore）、设置数据库密码。
3. 等 1-2 分钟初始化完成。
4. 左侧菜单 **SQL Editor** → New query，粘贴以下建表 SQL 并 Run：

```sql
create table if not exists visitors (
  id bigint generated always as identity primary key,
  visitor_id text unique not null,
  visit_count integer not null default 0,
  first_visit timestamptz,
  last_visit timestamptz
);
```

5. 左侧菜单 **Project Settings → API**，复制：
   - `Project URL` → 填入 `SUPABASE_URL`
   - `anon public` key → 填入 `SUPABASE_KEY`

> 安全性建议：匿名项目用 anon key 即可；若开启 Row Level Security，需为 `visitors` 表配置
> 允许匿名读写策略，或在服务端使用 service_role key（不要把 service_role key 暴露给前端）。

### 访问控制逻辑

- 每次点击「开始智能分析」前查询 `visit_count`，`>= 2` 则拒绝并提示
  “您已达到免费使用上限（2次），请联系管理员”。
- 每次成功分析后 `visit_count` +1，并更新 `last_visit`。
- 管理员输入 `ADMIN_PASSWORD` 后本会话不限次数，且不消耗计数。
- **降级方案**：Supabase 不可用时自动改用本地文件 `data/visitors.json` 计数，
  界面会提示“限制可能不跨设备/实例”。
  （Streamlit 是服务端应用，无法直接读写浏览器 localStorage，因此用服务端本地文件实现等效降级；
  如需严格浏览器 localStorage，可额外接入 `streamlit-js-eval` 组件。）

---

## 七、部署到 Streamlit Community Cloud

1. 把本项目推送到 GitHub 仓库：

```bash
git init
git add .
git commit -m "init data workbench"
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

2. 打开 [share.streamlit.io](https://share.streamlit.io)（用 GitHub 登录）→ **New app**。
3. 选择仓库、分支（main）、主文件（`app.py`），点 **Deploy**。
4. 部署成功后进入 **Settings → Secrets**，逐项粘贴：

```toml
ADMIN_PASSWORD = "你的管理员密码"
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJhbGci..."
MAX_ROWS = "300000"
```

5. 保存后应用会自动重启生效。

> 免费版说明：Streamlit Cloud 免费额度为约 1GB 内存、50GB 带宽/月、私密应用 1 个。
> 1700 万行明细不要直接整表载入，先在 SQL 里聚合（见下节）。

---

## 八、连接你的 1700 万行 MySQL 数据

你的 MySQL 数据库位于本机 `127.0.0.1:3306`，两种用法：

### 方案 A：本机运行（推荐，数据不出内网）

在装 MySQL 的机器上 `streamlit run app.py`，控制台里选「数据库连接」，
填入 `127.0.0.1 / 3306 / 数据库名 / 用户名 / 密码`，点击「测试连接」确认后写 SQL。

### 方案 B：云端部署 + 公网数据库

Streamlit Cloud 无法访问你家的 `127.0.0.1`。需要把数据库迁移/映射到公网可达地址
（云厂商 MySQL、内网穿透 + 白名单、或先导出聚合结果到 CSV 再上传）。

### 1700 万行的正确姿势：SQL 聚合（下推）

明细行数太大，建议在 SQL 中完成聚合，再交给工作台做四层分析。示例：

```sql
-- 按 配送日期 + 区域 + 品类 聚合（金额、数量、时效、订单数）
SELECT
    DATE(配送日期)                     AS 配送日期,
    区域,
    药品分类,
    COUNT(*)                           AS 订单数,
    SUM(数量)                          AS 数量,
    SUM(金额)                          AS 金额,
    AVG(配送时效)                      AS 平均配送时效
FROM 你的明细表
WHERE 配送日期 >= '2025-01-01'
GROUP BY DATE(配送日期), 区域, 药品分类
ORDER BY 配送日期;
```

工作台会自动把「配送日期/区域/药品分类」映射为 时间/空间/品类，
把「金额/数量」映射为度量，随后输出完整的四层报告。

> 数据库安全提醒：只读账号请保持只读权限；如果该密码已在对话中公开过，
> 建议尽快在 MySQL 中轮换密码，并限制只允许本机/白名单 IP 连接。

---

## 九、多行业适配说明

应用不硬编码业务字段，而是把输入自动映射为通用语义层：

| 语义角色 | 医药示例 | 零售示例 | 物流示例 |
| --- | --- | --- | --- |
| 主体 | 供应商 | 门店 | 承运方/仓库 |
| 客体 | 药品/SKU | 商品 | 运单/货物 |
| 时间 | 配送日期 | 销售日期 | 发运日期 |
| 空间 | 区域 | 商圈/区域 | 线路/区域 |
| 度量-金额 | 金额 | 销售额 | 运费 |
| 度量-数量 | 数量 | 销量 | 件量 |
| 时效 | 配送时效 | 到货时效 | 履约完成率 |

行业识别基于列名 + 抽样列值（如“药房”“胶囊”“配送时效”），
识别后自动切换报告里的业务叫法与专属策略建议。
同时识别**数据口径**：含“配送时效/履约”字段 → 配送口径；门店销售/实销类数据 → 实销口径。
报告与策略建议随口径调整——例如实销（门店销售）数据不会出现“配送时效合规”类建议，
而是给出动销、断货预警、效期管理等实销口径建议。

### 数据库英文缩写列名（如 delivery_datafull）

`delivery_datafull`（示例表，1,770 万行）使用纯英文缩写列名，已自动兼容识别：

| 列名 | 语义角色 |
| --- | --- |
| `biz_date` | 时间 |
| `down_cust_name` / `up_cust_name` / `group_cust_name` | 主体（下游/上游/集团客户） |
| `prod_name` / `generic_name` | 客体（商品/通用名） |
| `down_prov` / `prov_name` / `down_city` | 空间 |
| `total_price` | 度量-金额（`benchmark_price` 为基准单价，不会误识别为金额） |
| `quantity` / `std_quantity` | 度量-数量 |

建议 SQL（17,700,000 行明细，先聚合再分析）：

```sql
SELECT biz_date, down_prov, down_city, prod_name, cust_type_name,
       SUM(std_quantity) AS quantity, SUM(total_price) AS total_price
FROM delivery_datafull
WHERE biz_date >= '2024-01-01'
GROUP BY biz_date, down_prov, down_city, prod_name, cust_type_name;
```

> 提示：该表存在重复单据行（同一 bill_no 多条相同记录），分析前建议 `SELECT DISTINCT` 或按 `bill_no` 去重；
> MySQL `DECIMAL` 金额列已自动转为数值类型参与统计与相关性分析。

---

## 十、常见问题

- **普通访客用完 2 次怎么办？** 管理员在侧边栏输入密码后不限次数；管理员页可导出访客记录。
- **Supabase 没配会怎样？** 自动降级本地文件计数，界面有黄色提示。
- **图表用的是什么库？** 内置 `streamlit` 的图表 API + matplotlib 热力图，无需额外配置。
- **分析结果会保存吗？** 当前会话内存中保留，可下载 Markdown 报告；不落库、不采集业务数据。
- **时序图太密怎么办？** 预测分析页支持「时间粒度」切换（按月/按周/按日/按年）和「日期范围」下钻；
  默认按月预测，图例与纵轴余量已优化，任意窗口比例下峰值都可见。
- **热力图中文乱码怎么办？** 应用会自动注册系统自带中文字体（微软雅黑/黑体/苹方等）；若部署在无中文字体的
  服务器上，请安装 Noto Sans CJK 并重启。
- **改代码后仍报旧错误（如 time_series_analysis 缺 freq）？** 这是 Streamlit 长驻进程缓存了旧模块所致；
  应用已加入自动重载，仍建议完全停止（Ctrl+C）后重新 `streamlit run app.py`。
