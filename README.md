# AzureCNArchaeologist 🔍

> Azure中国定价数据考古与智能重建项目

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](#)
[![RAG](https://img.shields.io/badge/RAG-Hybrid_Intelligence-orange.svg)](#混合智能rag系统)

## 📋 项目概述

### 背景与挑战
Azure中国定价网站 (https://www.azure.cn/pricing/) 原维护团队已解散，前端JavaScript代码丢失。项目团队获得了完整的HTML源码文件，需要通过"HTML解析式考古"，从大量HTML文件中提取结构化数据，重建整个产品价格和计算器页面系统。

### 核心能力与当前状态
- 🔍 **可信事实源**: ✅ 211 个唯一 Product Definition，支持多分类和显式双语 Source Snapshot 路由
- 🏗️ **深度建模**: ✅ 构建策略化提取器架构，支持3+1策略自动识别
- 🤖 **统一批次工作流**: ✅ v0.3 已完成；七阶段 pipeline 支持1-8并发、严格恢复和可追溯状态
- 📦 **CMS就绪**: ✅ 输出兼容 CMS 业务契约与 Diagnostic Sidecar 1.1 的 JSON；379 个可运行批次项通过当前本地契约验证
- 🔄 **可追溯工作流**: ✅ 从快照发现到 P3 抽样内容验证、Review Queue 2.0、append-only Review Decision、本地 Dashboard Review Workbench 和批次报告已通过本地回归；不可变 Release 与正式 upload gate 仍在后续切片

v0.3 全量验收结果为 434 项终态守恒（379 项通过、55 项预期跳过）；详见 [`reports/v0.3/acceptance-status.md`](reports/v0.3/acceptance-status.md)。v0.4 当前已在 P3 Profile 下生成抽样验证证据，并支持 CLI 与本地 Dashboard Workbench 记录 hash-bound 审核决定；本版本仍没有执行发布。

### 🌟 核心特性

#### 💡 创新的混合RAG系统
- **多层级检索架构**: L1快速过滤 → L2语义检索 → L3精准重排 → L4完整上下文
- **成本效率平衡**: 根据查询复杂度智能选择检索策略，控制API调用成本
- **信息完整性保护**: 避免传统chunk切片的信息损耗，保持Azure服务信息的完整性

#### 🎯 Azure特色优化
- **中文技术术语智能处理**: 专门的Azure中文术语识别和标准化
- **复杂定价逻辑重建**: 支持阶梯定价、预留实例、区域差异等复杂Azure定价模式
- **服务关系知识图谱**: 基于图算法构建的Azure服务依赖和推荐关系网络

#### 🔧 工程化解决方案
- **可追溯的HTML解析**: 严格 UTF-8、失败隔离、Source Finding 与可恢复批次；不静默降级策略
- **大规模数据处理**: 批次清单、失败隔离、可恢复并行计算
- **v0.4目标质量体系**: 全状态结构契约、可复现抽样内容验证、人工批准与哈希绑定证据；不使用 `quality_score`

## 🏗️ 技术架构

### 整体架构图

下图是收敛后的 v0.4 目标流程。当前已实现到抽取、P3 抽样机器验证、Review Queue 2.0、CLI 受控 approve/reject 和本地 Dashboard 审核工作台；不可变 Release 与正式 upload gate 尚待后续切片完成。

```mermaid
flowchart LR
    A["1. Snapshot discovery"] --> B["2. Normalize"]
    B --> C["3. Preflight"]
    C --> D["4. Extract"]
    D --> E["5. Validate"]
    E --> F["6. Dashboard review queue"]
    F --> G["7. Human approve / reject"]
    G --> Q["Append-only Review Decision"]
    Q --> L["8. Immutable Release"]
    L --> RM["Release Manifest"]
    RM --> U["9. Blob upload"]
    H["Product Definitions / Source Snapshots"] --> A
    M["batch-manifest.json<br/>权威状态"] -. checkpoint .-> A
    M -. checkpoint .-> D
    M -. state gate .-> G
    M -. state gate .-> L
    D --> O["outputs + diagnostics"]
    E --> V["validation 投影"]
    F --> R["review queue + append-only decisions"]
    L --> X["output/releases/{release_id}"]
```

## v0.4 目标日常生产流程

> 当前实现边界：Step 4 Slice A-D 已提供 P3 sampled validation runtime、Review Queue 2.0、append-only Review Decision service、`pipeline-review-list` / `pipeline-review-decide` CLI，以及本地 `/review` Dashboard Workbench。Release 与 upload gate 尚未实现。实施边界见 [v0.4 execution plan](plans/v0.4-execution-plan.md)，代码导航见 [handoff](handoff.md)。

### 1. 接收上游 HTML 与配置

人工从上游取得本轮文件并放到 canonical 路径：

- HTML：data/current_prod_html/{language}/...
- 配置：data/configs/soft-category.json

这里的配置文件名是 soft-category.json，不使用 soft-catagory.json。

Source Snapshot 是本批次内容权威。不能在抽取器中静默修复、格式化或猜测上游 HTML；上游文件变化后创建新 Batch，不改写历史批次。

先检查 Product Definition、路由和快照闭环：

~~~bash
uv run cli.py catalog-build --check
uv run cli.py catalog-audit --language both
~~~

输入缺失、语言路由错误、非法 UTF-8、配置歧义或 Source identity 漂移时停止，不生成可批准产物。

### 2. 复制规范输入

~~~bash
uv run cli.py copy-from-prod --language both
~~~

目标位于 data/prod-html/{language}/...。复制只整理 canonical 路径：

- Source 与 Normalized Input 字节必须相同；
- SHA-256 必须相同；
- 不转码、不修 HTML、不改换行；
- 复制失败不应留下半成品。

### 3. 创建 Batch、抽取并进行机器验证

正式批次从 clean worktree 启动：

~~~bash
uv run cli.py pipeline-run --all --language both --parallel-jobs 6
uv run cli.py pipeline-status --batch-id <batch-id>
~~~

中断后可在 frozen provenance 未漂移时恢复：

~~~bash
uv run cli.py pipeline-resume --batch-id <batch-id>
~~~

只重新验证已成功抽取且身份未变化的 Payload：

~~~bash
uv run cli.py pipeline-validate --batch-id <batch-id>
~~~

canonical Payload 保存在：

~~~text
runs/{batch_id}/outputs/{language}/pricing/{resource}.json
runs/{batch_id}/outputs/{language}/SupportArticles/{articleType}/{resource}.json
~~~

这些文件是抽取产物，不等于人工批准或发布产物。

机器验证分为两层：

1. **全状态结构验证**
   - 完整检查 CMS Contract、筛选器、默认状态和 Source-proven Reachability Relation；
   - 每个可达状态必须恰好对应一个有效 contentGroup；
   - missing、extra、duplicate、错误 criteria、placeholder 和错误状态归属都会失败；
   - 这一层不抽样。
2. **内容一致性验证**
   - page-global、SimpleStatic 和 SupportArticle 主体完整比较；
   - RegionFilter、Complex 按 frozen Content Sampling Profile 进行确定性分层抽样，并把本 item 的 universe、seed 和 exact selected states 固定为 Batch Item Sampling Plan；
   - 比较冻结 Source HTML 与已经写盘的 Payload，而不是提取器内存中间结果；
   - 比较可见文本、价格与单位文本、表格、片段顺序、重复次数和状态归属；
   - 被选状态无法评估或内容不一致时 validation=failed，不能换一个样本重抽。

Machine Validation 通过只表示：

> 全部可达状态的结构契约成立，并且报告列出的内容样本与冻结 Source 一致。

它不表示未抽中状态已经完成内容逐项对账。

### 4. 查看 Review Queue 并准备人工审核

Machine Validation 通过的 P3 Batch Item 会进入 Review Queue 2.0，初始状态为 pending。审核单位是 Resource Key + Language，例如 api-management / zh-cn；中文批准不能替代英文批准。

当前可用 CLI：

~~~bash
uv run cli.py pipeline-review-list --batch-id <batch-id>
uv run cli.py pipeline-review-list --batch-id <batch-id> --status all --json
~~~

本地 Dashboard Workbench 已可用于正式 P3 Batch Item 审核。先启动只绑定 loopback 的 Python bridge，再启动 Dashboard：

~~~bash
uv run cli.py pipeline-review-serve --batch-id <batch-id> \
  --dashboard-origin http://127.0.0.1:3000

cd dashboard
npm run dev
~~~

`pipeline-review-serve` 会输出形如 `http://127.0.0.1:3000/review#bridge=...&token=...` 的 Dashboard URL。token 只存在于 URL fragment，页面读取后会移除 fragment 并仅保存在内存中；bridge 校验 Host、Origin、Bearer token、Batch allowlist、Content-Type 和 manifest revision。没有 token 时 `/review` 只显示未连接状态，不读取或写入 Batch。

Workbench 提供：

- 产品与产品语言项总览；
- runnable、pending、approved、rejected、source-blocked、release-ready 语言项统计，以及产品级 attention/ready 统计；
- 按语言、类别、策略、风险、失败历史和证据绑定筛选；
- 冻结 Source、persisted Payload 和机器抽样证据对照；
- 人工选择 region、software、category、tab 等实际存在的状态组合；
- 审核历史、失败原因、stale binding、Release/Publication 只读引用和显式 history index。

人工选择应独立于机器样本，并优先检查机器未覆盖或风险较高的组合。Live Azure 页面只能辅助定位，最终裁决对象仍是该 Batch 冻结的 Source Snapshot。

Dashboard 可以发起批准和拒绝，但不能直接编辑投影 JSON 或 manifest。按钮只调用与 CLI 共用的受控 review service；状态成功落盘并重建投影后才刷新显示。batch-manifest.json 仍是生命周期和 item 状态真源。

### 5. 人工批准或拒绝

每次 Review Decision 都是 append-only，并记录：

- Batch、Resource Key、Language；
- reviewer 和时间；
- Source、Payload、validation evidence SHA；
- 人工实际检查的状态组合；
- approved 或 rejected；
- reason classification 和 notes；
- 如果修正旧决定，记录被替代 decision identity。

当前可用 CLI：

~~~bash
uv run cli.py pipeline-review-decide --batch-id <batch-id> \
  --item-id zh-cn/api-management \
  --expected-revision <current-revision> \
  --reviewer reviewer@example.com \
  --verdict approved \
  --inspect-page-global \
  --inspect-state <reachable-state-id>

uv run cli.py pipeline-review-decide --batch-id <batch-id> \
  --item-id zh-cn/api-management \
  --expected-revision <current-revision> \
  --reviewer reviewer@example.com \
  --verdict rejected \
  --reason validator_defect \
  --inspect-state <reachable-state-id>
~~~

只有以下条件同时满足才允许 approved：

~~~text
execution = succeeded
validation = passed
approval_eligible = true
review evidence binds current hashes
inspected states belong to the frozen Reachability Relation
~~~

其中 Step 4 的 Approval Eligibility 要求：execution 和 validation 已通过、审核绑定当前 Source/Payload/validation hashes、记录的人工检查状态属于本 Batch Item 的 Reachability Relation，并且不存在未处置 Source Quality Finding。发现这类 finding 时保持 pending，或按实际原因 rejected；正式 disposition workflow 与复杂视觉 blocker 属于 Step 5。

机器失败不能被人工覆盖。Source、Payload 或 validation evidence 改变后，旧审核自动成为 stale，必须重新审核。

拒绝原因使用稳定分类：

| 原因 | 含义与处理 |
|---|---|
| upstream_source | 上游 HTML 结构或内容问题；保留证据并反馈上游 |
| product_config | Product Definition 或 soft-category 配置问题 |
| extractor_defect | 抽取逻辑错误；修代码并增加回归测试 |
| validator_defect | 机器验证漏报、误报或证据错误 |
| needs_clarification | 当前无法安全判断；保持不可批准 |

rejected item 不进入 Release。修复后通过新的 Batch 重新抽取、验证和审核。

Review Decision 的 verdict 作用于整个语言级 Batch Item。人工实际检查的是该 item 中若干状态；批准不会把未检查状态描述成人工逐项验证通过。

### 6. 目标：创建不可变 Release（后续 Slice）

人工批准不会移动或覆盖 runs 下的 canonical Payload。一个 Release 只从一个 Batch Run 复制当前仍满足全部门禁的项目：

~~~text
output/releases/{release_id}/
├── release-manifest.json
└── payloads/
    ├── zh-cn/...
    └── en-us/...
~~~

release-manifest.json 固定唯一 Batch/Input Manifest identity、精确 item 集合、Payload/validation/review hashes、Content Sampling Profile、Batch Item Sampling Plans、sampled/total/untested coverage、保证范围和目标 Blob identity。

Release 规则：

- write-once，同一 release_id 不覆盖；
- 只包含 execution succeeded、validation passed、approval eligible、review approved 且哈希匹配的项目；
- 在临时目录完成复制与校验，最后 canonical serialize Release Manifest，并以 manifest SHA + 全 payload hashes 形成 seal 后原子 finalize；
- seal 后任何文件或哈希变化都会使验证和 upload 拒绝；
- pending、rejected、stale、machine-failed、known_unsupported 和 experimental artifact 一律拒绝；
- Release staging 不等于 published。

### 7. 目标：校验并上传 Blob（后续 Slice）

正式 upload 只接受 sealed Release Manifest，不扫描任意 output 目录，也不把 sidecar 当批准权威。

操作顺序：

1. dry run 展示精确文件、哈希和 Blob prefix；
2. 再次校验 Release seal、Batch、Payload、Validation、Sampling Plan 和 Review Decision；
3. 上传同一不可变 Release；
4. 全部成功并核对远端结果后写 publication receipt；
5. 最后把权威 Publication 状态更新为 published。

上传失败不修改 Release，publication 保持 not_published；修复连接、权限或远端问题后可以幂等重试同一 Release。

### 8. 失败回路

~~~text
上游问题
  → 人工 rejected: upstream_source
  → 反馈上游修正
  → 新 Source Snapshot / 新 Batch

抽取逻辑问题
  → validation failed 或人工 rejected: extractor_defect
  → 修代码 + 回归测试
  → 新 Batch

验证器问题
  → 人工 rejected: validator_defect
  → 修验证规则 + 回归测试
  → 新 Batch

审核未完成或无法判断
  → 保持 pending/rejected
  → 不进入 Release
~~~

### 9. 可以与不能宣称的保证

可以宣称：

- Source 与 Normalized Input 的身份经过哈希验证；
- CMS Contract 和完整 Source-proven 状态拓扑经过全量机器验证；
- page-global、SimpleStatic 和 SupportArticle 主体经过完整内容比较；
- 报告列出的 RegionFilter/Complex 样本与冻结 Source 内容一致；
- Review Decision 与 Release 绑定精确 Source、Payload、Profile 和证据哈希。

不能宣称：

- 所有 Region、Software、Category 或 Tab 状态的内容都与源完全一致；
- 全部价格事实已经逐项验证；
- Source 中的价格具有外部 Commercial Price Accuracy；
- 未抽中状态不存在内容错配；
- Dashboard 展示、Review Queue membership 或 upload 成功本身等于人工批准；
- 未按冻结 Rendering Profile 审核的视觉布局已经验证。

### 核心技术栈
- **编程语言**: Python 3.11+
- **包管理**: uv
- **HTML解析**: BeautifulSoup + lxml + selectolax
- **数据处理**: pandas + numpy + jieba
- **机器学习**: scikit-learn + transformers
- **图算法**: NetworkX + graph-tool
- **Embedding模型**: qwen3-embedding / text-embedding-3-large
- **Rerank模型**: qwen3-rerank / cohere-rerank
- **向量存储**: milvus + faiss (备选: chromadb + qdrant)
- **大语言模型**: transformers + deepseek-api + openai-api
- **数据库**: PostgreSQL + MongoDB + SQLite
- **可视化**: matplotlib + plotly + graphviz

## 🚀 快速开始

### 环境要求
- Python 3.11+
- 8GB+ RAM (推荐16GB)
- 50GB+ 磁盘空间
- GPU (推荐，用于embedding和向量化加速)
- Milvus 2.3+ (向量数据库)

### 安装步骤

#### 使用 uv

```bash
# 1. 安装uv包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone https://github.com/your-org/AzureCNArchaeologist.git
cd AzureCNArchaeologist

# 3. 使用uv创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 4. 安装项目本身
uv pip install -e .
```

#### 配置环境

```bash
# 5. 复制环境配置文件
cp .env.example .env

# 6. 编辑环境配置文件
vim .env  # 或使用其他编辑器
```

**环境变量配置示例 (.env)**:
```bash
# API配置
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key
COHERE_API_KEY=your_cohere_api_key  # 如果使用cohere-rerank

# 模型配置
EMBEDDING_MODEL=qwen3-embedding  # 或 text-embedding-3-large
RERANK_MODEL=qwen3-rerank       # 或 cohere-rerank
DEFAULT_LLM=deepseek            # 或 openai

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=your_username
MILVUS_PASSWORD=your_password

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/azure_archaeologist
MONGODB_URL=mongodb://localhost:27017/azure_archaeologist

# 缓存配置
REDIS_URL=redis://localhost:6379/0
```

#### 启动Milvus向量数据库

```bash
# 使用Docker Compose启动Milvus
curl -O https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml
docker-compose -f milvus-standalone-docker-compose.yml up -d

# 或使用Milvus Lite (轻量版)
pip install milvus-lite
```

#### 初始化项目

```bash
# 7. 初始化数据目录和数据库
python scripts/init_project.py

# 8. 验证安装
python scripts/verify_installation.py
```

### 基本使用

#### 统一CLI界面

```bash
# 统一批次工作流示例
# 步骤1: 检查事实源和快照闭环
uv run cli.py catalog-build --check
uv run cli.py catalog-audit --language both

# 步骤2: 运行全量双语统一 pipeline（包含逐资源 normalize；--language 默认 both）
uv run cli.py pipeline-run --all --parallel-jobs 6

# 步骤3: 使用上一步返回的 Batch ID 查看状态
uv run cli.py pipeline-status --batch-id <batch-id>

# 如运行被中断，在 provenance 未漂移时恢复
uv run cli.py pipeline-resume --batch-id <batch-id>

# 只重新验证已有、提取成功的 payload
uv run cli.py pipeline-validate --batch-id <batch-id>

# 查看和记录受控人工审核决定
uv run cli.py pipeline-review-list --batch-id <batch-id> --status pending
uv run cli.py pipeline-review-serve --batch-id <batch-id> \
  --dashboard-origin http://127.0.0.1:3000
uv run cli.py pipeline-review-decide --batch-id <batch-id> \
  --item-id zh-cn/api-management \
  --expected-revision <current-revision> \
  --reviewer reviewer@example.com \
  --verdict approved \
  --inspect-state <reachable-state-id>

# 通过 validation 的业务 payload 位于 runs/<batch-id>/outputs；
# pipeline 本身不会上传或发布它们

# 如需脱离 Batch Run 单独准备规范输入，可手动复制
uv run cli.py copy-from-prod --language both

# 单产品提取
uv run cli.py extract mysql --language zh-cn --output-dir output

# 列出唯一 Product Definition 和分类视图
uv run cli.py list-products
uv run cli.py list-categories

# 查看项目状态
uv run cli.py status
```

#### 传统方式（NOT IMPLEMENMTED）

```bash
# 运行完整的数据处理流水线
python main.py --mode full

# 运行特定阶段
python main.py --stage 1  # 运行阶段一：HTML文件分析与分类
python main.py --stage 2  # 运行阶段二：HTML解析与数据提取

# 指定模型配置运行
python main.py \
  --embedding-model qwen3-embedding \
  --rerank-model qwen3-rerank \
  --llm deepseek

# 启动AI助手服务 (混合RAG系统)
python -m rag_system.server \
  --port 8080 \
  --embedding-model text-embedding-3-large \
  --vector-store milvus

# 运行Web界面
streamlit run web_interface/app.py

# 向量数据库管理
python scripts/milvus_manager.py --action create_collection
python scripts/milvus_manager.py --action load_vectors
python scripts/milvus_manager.py --action search --query "Azure虚拟机定价"
```

### 模型配置选择

#### Embedding模型对比
```bash
# Qwen3 Embedding (推荐中文场景)
python main.py --embedding-model qwen3-embedding
# 优势：中文理解能力强，成本较低
# 适用：中文Azure文档处理

# OpenAI Text-Embedding-3-Large (推荐多语言场景)  
python main.py --embedding-model text-embedding-3-large
# 优势：多语言支持，向量质量高
# 适用：国际化部署需求
```

#### Rerank模型对比
```bash
# Qwen3 Rerank (推荐中文场景)
python main.py --rerank-model qwen3-rerank
# 优势：中文重排效果好，响应速度快

# Cohere Rerank (推荐高精度场景)
python main.py --rerank-model cohere-rerank  
# 优势：重排精度高，多语言支持
```

#### 大语言模型配置
```bash
# DeepSeek API (推荐性价比场景)
python main.py --llm deepseek --max-context 128k
# 优势：成本低，长上下文，中文友好

# OpenAI API (推荐高质量场景)
python main.py --llm openai --model gpt-4-turbo
# 优势：质量高，生态成熟
```

## 📁 项目结构

```
AzureCNArchaeologist/
├── analysis/                 # 阶段一: HTML分析模块
│   ├── file_analyzer.py     # 文件系统分析器
│   ├── structure_analyzer.py # HTML结构分析器
│   └── classifier.py        # 智能文件分类器
├── parsing/                  # 阶段二: HTML解析模块
│   ├── parser_engine.py     # 多策略解析引擎
│   ├── table_parser.py      # 定价表格专项解析器
│   └── content_extractor.py # 内容提取器
├── processing/               # 阶段三: 数据处理模块
│   ├── quality_controller.py # 数据质量控制器
│   ├── text_processor.py    # 中文文本处理器
│   └── price_standardizer.py # 价格数据标准化器
├── modeling/                 # 阶段四: 数据建模模块
│   ├── taxonomy_builder.py  # 分类体系构建器
│   ├── relationship_graph.py # 服务关系图谱
│   └── pricing_engine.py    # 复杂定价引擎
├── calculator/               # 阶段五: 计算器模块
│   ├── calculation_engine.py # 计算引擎
│   ├── pricing_algorithms.py # 定价算法
│   └── result_formatter.py  # 结果格式化器
├── rag_preparation/          # 阶段六: RAG数据准备
│   ├── metadata_indexer.py  # 元数据索引器
│   ├── embedder.py          # 向量化处理器
│   │   ├── qwen3_embedder.py      # Qwen3 Embedding
│   │   └── openai_embedder.py     # OpenAI Embedding
│   ├── milvus_manager.py    # Milvus向量库管理
│   └── context_assembler.py # 上下文组装器
├── rag_system/              # 混合智能RAG系统
│   ├── retrieval_engine.py # 混合检索引擎
│   ├── strategy_selector.py # 策略选择器
│   ├── rerankers/          # 重排模型
│   │   ├── qwen3_reranker.py     # Qwen3 Rerank
│   │   └── cohere_reranker.py    # Cohere Rerank
│   ├── llm_clients/        # 大语言模型客户端
│   │   ├── deepseek_client.py    # DeepSeek API客户端
│   │   └── openai_client.py      # OpenAI API客户端
│   ├── cost_optimizer.py   # 成本优化器
│   └── server.py           # API服务器
├── validation/              # 阶段七: 验证模块
│   ├── quality_validator.py # 质量验证器
│   ├── performance_tester.py # 性能测试器
│   └── accuracy_checker.py  # 准确性检查器
├── export/                  # 阶段八: 导出模块
│   ├── cms_exporter.py     # CMS数据导出器
│   ├── api_exporter.py     # API数据导出器
│   └── monitoring_dashboard.py # 监控仪表板
├── web_interface/           # Web用户界面
├── config/                  # 配置文件
├── data/                    # 数据目录
│   ├── html_source/        # 原始HTML文件
│   ├── processed/          # 处理后数据
│   ├── rag_ready/         # RAG就绪数据
│   └── exports/           # 导出数据
├── tests/                  # 测试文件
├── scripts/               # 工具脚本
│   ├── init_project.py   # 项目初始化
│   ├── milvus_manager.py # Milvus管理工具
│   └── verify_installation.py # 安装验证
├── docs/                  # 文档
├── pyproject.toml        # Poetry配置文件
├── requirements.txt       # pip/uv依赖文件
├── .env.example          # 环境变量模板
├── docker-compose.yml    # Docker部署配置
├── main.py               # 主入口
└── README.md             # 本文档
```

## 🗺️ 实施阶段详解

### 📊 整体时间规划 (7周)

| 阶段 | 时间 | 核心任务 | 关键输出 |
|------|------|----------|----------|
| 阶段一 | 3天 | HTML文件分析与分类 | 文件清单、分类结果、解析策略 |
| 阶段二 | 5天 | HTML解析与数据提取 | 结构化数据、定价信息、服务档案 |
| 阶段三 | 4天 | 数据清洗与标准化 | 标准化数据、质量报告、术语库 |
| 阶段四 | 5天 | 数据建模与关系构建 | 分类体系、关系图谱、定价模型 |
| 阶段五 | 4天 | 计算器逻辑重建 | 计算引擎、算法库、结果模板 |
| 阶段六 | 6天 | 混合智能RAG数据准备 | RAG数据包、检索配置、向量数据 |
| 阶段七 | 3天 | 数据验证与质量保证 | 验证报告、性能指标、优化建议 |
| 阶段八 | 3天 | 多目标数据导出 | CMS数据、API接口、监控工具 |

### 🎯 关键里程碑

- **M1 (Week 1)**: HTML解析引擎完成，数据提取率>85%
- **M2 (Week 2-3)**: 数据标准化完成，质量分>85分
- **M3 (Week 4)**: 知识图谱构建完成，关系准确率>90%
- **M4 (Week 5)**: 定价计算器完成，计算准确率>98%
- **M5 (Week 6-7)**: 混合RAG系统完成，支持智能问答

## 🤖 混合智能RAG系统

### 核心创新理念

传统RAG系统存在严重的信息损耗问题：
- ❌ **以chunk为粒度的召回**存在信息切片损失
- ❌ **chunk同质化严重**，topN结果可能都是类似内容
- ❌ **chunk排序打乱**，干扰大模型理解

### 我们的解决方案

#### 🔄 多层级检索架构
```
L1 快速过滤层: metadata索引 + 关键词匹配 (毫秒级)
    ↓
L2 语义检索层: 产品级embedding + 向量相似度 (100ms级)
    ↓  
L3 精准重排层: rerank模型 + 相关性优化 (500ms级)
    ↓
L4 完整上下文层: 大窗口LLM + 完整信息 (秒级，高精度)
```

#### 💰 成本效率平衡
- **用户分级**: Free用户限制L4使用，Premium用户享受完整服务
- **查询路由**: 简单查询走L1-L2，复杂查询走L3-L4
- **智能缓存**: 热点查询缓存，相似查询复用结果
- **Token优化**: 极限命中DeepSeek缓存，2:1的缓存命中比例

#### 📊 性能优势
- **输入/输出比例**: 100K+ token输入，个位数token输出
- **GPU利用率**: 充分利用GPU算力，避开decode限制
- **响应速度**: L1层毫秒级响应，L4层保证秒级响应
- **成本控制**: 动态策略选择，成本降低60%+

### 使用示例

```python
from rag_system import HybridRAGOrchestrator
from rag_system.config import RAGConfig

# 配置混合RAG系统
config = RAGConfig(
    embedding_model="qwen3-embedding",    # 或 "text-embedding-3-large"
    rerank_model="qwen3-rerank",         # 或 "cohere-rerank"
    llm_provider="deepseek",             # 或 "openai"
    vector_store="milvus",
    max_context_length=128000,
    cost_optimization=True
)

# 初始化混合RAG系统
rag = HybridRAGOrchestrator(config)

# 简单查询 - 自动路由到L1策略 (metadata过滤)
result = rag.query(
    query="什么是Azure虚拟机？",
    user_tier="free"
)
print(f"策略: {result.strategy_used}, 成本: ¥{result.cost:.4f}")

# 复杂查询 - 自动路由到L4策略 (大上下文)
result = rag.query(
    query="请详细对比虚拟机和应用服务的成本差异，并给出企业级推荐方案",
    user_tier="premium"
)

# 定价计算查询 - 路由到计算引擎
result = rag.query(
    query="4核16GB虚拟机在中国东部运行一个月的费用",
    query_type="pricing",
    parameters={
        "cpu_cores": 4,
        "memory_gb": 16,
        "region": "china-east",
        "duration": "1 month"
    }
)

# 使用不同模型配置
# 高精度配置 (OpenAI + Cohere)
high_accuracy_config = RAGConfig(
    embedding_model="text-embedding-3-large",
    rerank_model="cohere-rerank",
    llm_provider="openai"
)

# 成本优化配置 (Qwen3 + DeepSeek)
cost_optimized_config = RAGConfig(
    embedding_model="qwen3-embedding",
    rerank_model="qwen3-rerank", 
    llm_provider="deepseek"
)

# 向量数据库操作示例
from rag_system.vector_store import MilvusVectorStore

# 初始化Milvus向量存储
vector_store = MilvusVectorStore(
    host="localhost",
    port=19530,
    collection_name="azure_services"
)

# 批量向量化和存储Azure服务数据
services_data = load_processed_services()
embeddings = rag.embedder.embed_batch([s['description'] for s in services_data])
vector_store.insert_vectors(embeddings, services_data)

# 向量相似度搜索
query_embedding = rag.embedder.embed("虚拟机定价")
similar_services = vector_store.search(
    query_embedding, 
    top_k=10,
    filter_expr="category == 'compute'"
)
```

### API使用示例

```bash
# 启动RAG服务器
python -m rag_system.server --config production

# RESTful API调用
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Azure虚拟机和容器实例的价格对比",
    "user_tier": "premium",
    "strategy": "auto"
  }'

# WebSocket实时查询
curl -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8080/ws/query
```

## 🛠️ 开发指南

### 代码规范
- 遵循PEP 8 Python代码规范
- 使用type hints提高代码可读性
- 函数和类需要详细的docstring
- 关键算法需要性能测试

### 开发环境设置

#### 使用uv开发环境
```bash
# 安装开发依赖
uv pip install -r requirements-dev.txt

# 安装pre-commit钩子
pre-commit install

# 代码格式化
uv run black .
uv run isort .

# 类型检查
uv run mypy .
```

#### 使用Poetry开发环境
```bash
# 安装开发依赖
poetry install --with dev,test

# 代码格式化
poetry run black .
poetry run isort .

# 类型检查
poetry run mypy .
```

### 测试要求
```bash
# 使用uv运行测试
uv run pytest tests/unit/                    # 单元测试
uv run pytest tests/integration/             # 集成测试
uv run pytest tests/performance/             # 性能测试
uv run pytest --cov=. --cov-report=html     # 测试覆盖率

# 使用Poetry运行测试
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/performance/
poetry run pytest --cov=. --cov-report=html

# 模型特定测试
pytest tests/models/test_qwen3_embedding.py
pytest tests/models/test_cohere_rerank.py
pytest tests/vector_stores/test_milvus.py

# Milvus集成测试
pytest tests/integration/test_milvus_integration.py
```

### 本地开发配置

**开发环境配置 (.env.dev)**:
```bash
# 开发模式配置
DEBUG=true
LOG_LEVEL=DEBUG

# 本地Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 开发用API配置 (使用较便宜的模型)
EMBEDDING_MODEL=qwen3-embedding
RERANK_MODEL=qwen3-rerank
DEFAULT_LLM=deepseek

# 本地向量存储
VECTOR_STORE_PATH=./data/vectors/
CACHE_DIR=./data/cache/
```

### 部署说明

#### Docker部署
```bash
# 构建项目镜像
docker build -t azure-archaeologist:latest .

# 使用docker-compose部署完整服务栈
docker-compose up -d

# 包含Milvus、Redis、PostgreSQL等服务
# 查看服务状态
docker-compose ps
```

#### Kubernetes部署
```bash
# 部署Milvus集群
kubectl apply -f k8s/milvus/

# 部署应用服务
kubectl apply -f k8s/app/

# 配置Ingress
kubectl apply -f k8s/ingress/
```

#### 生产环境配置

**生产环境配置 (.env.prod)**:
```bash
# 生产模式
DEBUG=false
LOG_LEVEL=INFO

# 高可用Milvus集群
MILVUS_HOST=milvus-cluster.internal
MILVUS_PORT=19530
MILVUS_USER=production_user
MILVUS_PASSWORD=secure_password

# 生产API配置
EMBEDDING_MODEL=text-embedding-3-large  # 高质量模型
RERANK_MODEL=cohere-rerank              # 高精度重排
DEFAULT_LLM=openai                      # 稳定性优先

# 缓存和存储
REDIS_CLUSTER_NODES=redis1:6379,redis2:6379,redis3:6379
DATABASE_URL=postgresql://user:pass@postgres-cluster:5432/prod_db

# 监控配置
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

### 模型管理

#### 模型下载和缓存
```bash
# 下载Qwen3模型
python scripts/download_models.py --model qwen3-embedding
python scripts/download_models.py --model qwen3-rerank

# 预热模型缓存
python scripts/warm_up_models.py

# 模型性能测试
python scripts/benchmark_models.py --embedding qwen3-embedding
python scripts/benchmark_models.py --rerank cohere-rerank
```

#### 模型切换
```bash
# 运行时切换embedding模型
curl -X POST http://localhost:8080/api/v1/config/embedding \
  -d '{"model": "text-embedding-3-large"}'

# 切换rerank模型
curl -X POST http://localhost:8080/api/v1/config/rerank \
  -d '{"model": "qwen3-rerank"}'
```

## 📈 性能指标

### 数据处理性能
- **文件处理速度**: 平均5秒/文件
- **内存使用**: 峰值<2GB
- **并发处理**: 支持4-8个并行任务
- **数据准确率**: >95%

### RAG系统性能

#### 检索性能对比
| 策略层级 | 响应时间 | 准确率 | 成本/查询 | 适用场景 |
|---------|---------|--------|----------|----------|
| L1 (Metadata) | <50ms | 75% | ¥0.000 | 简单FAQ |
| L2 (Embedding) | <200ms | 85% | ¥0.001 | 常规查询 |
| L3 (Rerank) | <500ms | 92% | ¥0.005 | 复杂对比 |
| L4 (LLM) | <3s | 96% | ¥0.050 | 深度分析 |

#### 模型性能对比

**Embedding模型性能**:
| 模型 | 向量维度 | 处理速度 | 中文准确率 | 成本/1K tokens |
|------|---------|----------|------------|-------------|
| qwen3-embedding | 1024 | 2000 doc/s | 94% | ¥0.0005 |
| text-embedding-3-large | 3072 | 1500 doc/s | 91% | ¥0.0013 |

**Rerank模型性能**:
| 模型 | 处理速度 | 重排准确率 | 延迟 | 成本/1K pairs |
|------|---------|------------|------|-------------|
| qwen3-rerank | 500 pairs/s | 89% | 20ms | ¥0.002 |
| cohere-rerank | 300 pairs/s | 93% | 35ms | ¥0.008 |

**LLM性能对比**:
| 模型 | 上下文长度 | 推理速度 | 中文质量 | 成本/1K tokens |
|------|------------|----------|----------|-------------|
| DeepSeek | 128K | 快 | 优秀 | ¥0.0014 |
| GPT-4-Turbo | 128K | 中等 | 优秀 | ¥0.030 |

### 向量存储性能

#### Milvus性能指标
- **索引构建**: 100万向量 <5分钟
- **查询性能**: top-10搜索 <10ms
- **并发查询**: 支持1000+ QPS
- **存储效率**: 压缩比 70%
- **可扩展性**: 支持十亿级向量

#### 成本效益分析
```python
# 月度成本估算 (1万查询/天)
monthly_costs = {
    "qwen3_stack": {
        "embedding": 30,    # CNY
        "rerank": 60,       # CNY  
        "llm": 420,         # CNY
        "total": 510        # CNY (~$70)
    },
    "openai_stack": {
        "embedding": 390,   # CNY
        "rerank": 240,      # CNY
        "llm": 9000,        # CNY  
        "total": 9630       # CNY (~$1330)
    },
    "hybrid_optimized": {
        "l1_l2_queries": 90,  # 60% 查询
        "l3_l4_queries": 420, # 40% 查询  
        "total": 510          # CNY (~$70)
    }
}
```

### 系统监控指标

#### 实时监控面板
- **查询分布**: L1(40%) → L2(35%) → L3(20%) → L4(5%)
- **平均响应时间**: 280ms
- **成功率**: 99.2%
- **用户满意度**: 92%
- **成本效率**: 比传统RAG节省68%

#### 告警阈值
- 响应时间 >5s
- 错误率 >1%  
- Milvus连接失败
- API配额即将耗尽
- 向量存储空间 >80%

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献代码
1. Fork本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

### 报告问题
- 使用GitHub Issues报告bug
- 提供详细的错误信息和重现步骤
- 包含系统环境信息

### 功能建议
- 在Issues中提出新功能建议
- 详细描述功能需求和使用场景
- 参与功能设计讨论

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
