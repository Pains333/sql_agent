<div align="center">

# 🤖 SQL Agent

**An intelligent database assistant powered by LLM — operate databases with natural language.**

[中文](#中文文档) · [English](#english-documentation)

</div>

---

## 中文文档

### 📖 简介

SQL Agent 是一个基于大语言模型（LLM）的智能数据库助手。用户只需用自然语言描述需求，AI 会自动生成并执行 SQL 语句，支持建表、查询、数据导入等操作。

### ✨ 功能特性

- **🗣️ 自然语言转 SQL** — 用中文或英文描述需求，AI 自动生成 SQL 并执行
- **📊 多数据库支持** — 支持 PostgreSQL、MySQL、Oracle，以及本地文件型数据库 **SQLite**、**DuckDB**
- **🤖 多模型支持** — 支持本地 Ollama 模型或第三方 API
- **🕸️ 数据血缘追踪** — 智能解析 SQL 提取表级与字段级血缘关系，并支持全屏可视化沉浸式画板体验
- **🗺️ 数据库 ER 图** — 实时生成并渲染数据库表结构实体关系图（ER Diagram），直观掌握数据库架构
- **⚡ 多任务并发处理** — 前后端流式状态解耦，支持在多个对话框中同时派发长耗时 SQL 任务，真正无阻塞的多线程体验
- **🛡️ 智能防冲突机制** — 建表时若遇重名，AI 会自动为您加上 `_v2`、`_new` 等后缀，并自动修正所有外键关联
- **🔒 跨库上下文隔离** — 切换数据库时，专属的数据字典、对话历史、表结构概览实现完美隔离，杜绝大模型“记忆串线”
- **📎 附件数据导入** — 上传 Excel / CSV / Parquet / JSON 文件，智能匹配表结构并批量写入
- **📚 业务数据字典** — 自定义专有业务名词解释与枚举字段映射，无缝集成到 LLM 上下文中
- **🧠 自动纠错机制** — AI 自动捕获 SQL 报错并尝试修复重试，提升执行成功率
- **🚀 RAG 大表优化** — 基于本地轻量级 TF-IDF 的表结构检索引擎，防止数百张表导致 Token 上下文溢出
- **📝 自动元数据管理** — 自动维护 `skill.md` 文件，实时与真实物理数据库强同步
- **💬 多会话管理** — 支持创建、切换、删除多个对话
- **🌐 中英文双语** — 界面完整支持中文和英文切换
- **⚙️ 配置持久化** — 配置自动保存，重启后无需重新设置
- **🎨 现代化 UI** — 基于 React + TypeScript 的简洁白色主题界面

### 🚀 快速开始

#### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL / MySQL / Oracle / SQLite / DuckDB（任选其一）
- [Ollama](https://ollama.ai/)（如使用本地模型）或者第三方 API

#### 1. 克隆项目

```bash
git clone https://github.com/your-username/sql_agent.git
cd sql_agent
```

#### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

#### 3. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

#### 4. 启动后端

```bash
python3 -m backend.server
```

#### 5. 启动前端

```bash
cd frontend
npm run dev
```

### 📎 附件导入功能

支持上传以下格式的文件并导入到数据库表：

| 格式 | 扩展名 |
|------|--------|
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Parquet | `.parquet` |
| JSON | `.json` |

**导入规则：**
- 自增字段（如 `id`）自动跳过，由数据库生成
- NOT NULL 字段必须在附件中存在对应列，否则报错
- 可空字段如果附件中不存在，自动填充 `NULL`
- 附件中多余的列（表中不存在的）自动忽略

## English Documentation

### 📖 Introduction

SQL Agent is an intelligent database assistant powered by Large Language Models (LLMs). Describe what you need in natural language, and AI will automatically generate and execute SQL statements — supporting table creation, queries, data imports, and more.

### ✨ Features

- **🗣️ Natural Language to SQL** — Describe your needs in plain language, AI generates and executes SQL
- **📊 Multi-Database Support** — PostgreSQL, MySQL, Oracle, and local file DBs **SQLite**, **DuckDB**
- **🤖 Multi-Model Support** — Local Ollama models or APIs
- **🕸️ Data Lineage Tracking** — Smartly parse SQL to extract table and column-level lineage relationships with full-screen visualization capabilities
- **🗺️ ER Diagram Generation** — Real-time entity-relationship diagram visualization to intuitively explore database schemas
- **⚡ True Concurrent Tasks** — Decoupled frontend streaming states allow you to run and monitor multiple complex SQL tasks simultaneously across different chats without UI blocking
- **🛡️ Smart Collision Avoidance** — AI automatically appends `_v2` or `_new` suffixes to table names and updates foreign keys if a naming conflict occurs during table creation
- **🔒 Strict Cross-DB Isolation** — Data dictionaries, conversation histories, and schema contexts are perfectly isolated when switching databases, preventing LLM memory bleed
- **📎 File Data Import** — Upload Excel / CSV / Parquet / JSON files with intelligent column matching
- **📚 Business Data Dictionary** — Customize proprietary business terms and field mappings natively injected into LLM context
- **🧠 Auto-Fix Mechanism** — AI automatically catches SQL errors and attempts to fix them transparently
- **🚀 RAG Optimization** — Lightweight local TF-IDF table retriever to prevent context overflow with large databases
- **📝 Auto Metadata Management** — Automatically maintains `skill.md`, strictly synchronized with the physical database state
- **💬 Multi-Session Chat** — Create, switch, and delete multiple conversations
- **🌐 Bilingual UI** — Full Chinese and English interface support
- **⚙️ Persistent Configuration** — Settings auto-saved, no reconfiguration needed after restart
- **🎨 Modern UI** — Clean white theme built with React + TypeScript

### 🚀 Quick Start

#### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL / MySQL / Oracle / SQLite / DuckDB (any one)
- [Ollama](https://ollama.ai/) (if using local models) or APIs

#### 1. Clone the repository

```bash
git clone https://github.com/your-username/sql_agent.git
cd sql_agent
```

#### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

#### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

#### 4. Start the backend

```bash
python3 -m backend.server
```

#### 5. Start the frontend

```bash
cd frontend
npm run dev
```

### 📎 File Import

Supported file formats for data import:

| Format | Extension |
|--------|-----------|
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Parquet | `.parquet` |
| JSON | `.json` |

**Import Rules:**
- Auto-increment fields (e.g., `id`) are skipped — generated by the database
- NOT NULL fields must have matching columns in the file, otherwise an error is raised
- Nullable fields missing from the file are filled with `NULL`
- Extra columns in the file (not in the table) are silently ignored

<div align="center">

### 📄 License

MIT License

</div>
