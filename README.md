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
- **📊 多数据库支持** — 支持 PostgreSQL、MySQL、Oracle
- **🤖 多模型支持** — 支持本地 Ollama 模型或 OpenAI 兼容 API
- **📎 附件数据导入** — 上传 Excel / CSV / Parquet / JSON / PKL 文件，智能匹配表结构并批量写入
- **📝 自动元数据管理** — 自动维护 `skill.md` 文件，记录所有数据库和表的结构信息
- **💬 多会话管理** — 支持创建、切换、删除多个对话
- **🌐 中英文双语** — 界面完整支持中文和英文切换
- **⚙️ 配置持久化** — 配置自动保存，重启后无需重新设置
- **🎨 现代化 UI** — 基于 React + TypeScript 的简洁白色主题界面

### 🏗️ 技术架构

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│          React + TypeScript + Vite           │
│                :5173                         │
├─────────────────────────────────────────────┤
│                  Backend                     │
│            FastAPI + Uvicorn                 │
│                :8000                         │
├──────────┬──────────┬───────────────────────┤
│  Agent   │ LLM Client│    DB Client         │
│ (核心调度) │(Ollama/API)│ (PostgreSQL/MySQL)  │
├──────────┴──────────┴───────────────────────┤
│       Skill Manager  │  Data Importer       │
│    (元数据管理)        │  (文件解析+导入)      │
└─────────────────────────────────────────────┘
```

### 📁 项目结构

```
sql_agent/
├── server.py              # FastAPI 后端服务
├── agent.py               # Agent 核心逻辑（调度 LLM + DB）
├── llm_client.py          # LLM 客户端（Ollama / OpenAI API）
├── db_client.py           # 数据库客户端（多数据库支持）
├── prompts.py             # LLM 提示词模板
├── skill_manager.py       # skill.md 元数据管理
├── file_parser.py         # 文件解析器（Excel/CSV/Parquet/JSON/PKL）
├── data_importer.py       # 数据导入器（列匹配 + 批量写入）
├── conversation_store.py  # 对话持久化存储
├── config.py              # 配置文件
├── main.py                # CLI 模式入口
├── requirements.txt       # Python 依赖
├── skill.md               # 数据库元信息（自动维护）
└── frontend/              # React 前端
    ├── src/
    │   ├── App.tsx         # 根组件
    │   ├── api.ts          # API 客户端
    │   ├── i18n.ts         # 国际化（中/英）
    │   ├── types.ts        # TypeScript 类型定义
    │   └── components/
    │       ├── ChatArea.tsx       # 聊天区域（含附件上传）
    │       ├── Sidebar.tsx        # 侧边栏（会话管理）
    │       ├── SetupWizard.tsx    # 初始配置向导
    │       ├── MessageBubble.tsx  # 消息气泡
    │       └── ContextMenu.tsx    # 右键菜单
    └── package.json
```

### 🚀 快速开始

#### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL / MySQL / Oracle（任选其一）
- [Ollama](https://ollama.ai/)（如使用本地模型）

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
python server.py
```

#### 5. 启动前端

```bash
cd frontend
npm run dev
```

#### 6. 打开浏览器

访问 [http://localhost:5173](http://localhost:5173)，按照配置向导完成初始设置。

### 📎 附件导入功能

支持上传以下格式的文件并导入到数据库表：

| 格式 | 扩展名 |
|------|--------|
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Parquet | `.parquet` |
| JSON | `.json` |
| Pickle | `.pkl` |

**导入规则：**
- 自增字段（如 `id`）自动跳过，由数据库生成
- NOT NULL 字段必须在附件中存在对应列，否则报错
- 可空字段如果附件中不存在，自动填充 `NULL`
- 附件中多余的列（表中不存在的）自动忽略

### ⚙️ 配置说明

首次启动时，配置向导会引导你完成以下设置：

| 配置项 | 说明 |
|--------|------|
| 语言 | 中文 / English |
| 模型来源 | 本地 Ollama 或 API |
| 模型名称 | 如 `gemma4:31b`、`gpt-4o` 等 |
| 数据库类型 | PostgreSQL / MySQL / Oracle |
| 连接信息 | 主机、端口、用户名、密码 |

配置保存在 `setup_config.json`，重启后自动加载。

---

## English Documentation

### 📖 Introduction

SQL Agent is an intelligent database assistant powered by Large Language Models (LLMs). Describe what you need in natural language, and AI will automatically generate and execute SQL statements — supporting table creation, queries, data imports, and more.

### ✨ Features

- **🗣️ Natural Language to SQL** — Describe your needs in plain language, AI generates and executes SQL
- **📊 Multi-Database Support** — PostgreSQL, MySQL, Oracle
- **🤖 Multi-Model Support** — Local Ollama models or OpenAI-compatible APIs
- **📎 File Data Import** — Upload Excel / CSV / Parquet / JSON / PKL files with intelligent column matching
- **📝 Auto Metadata Management** — Automatically maintains `skill.md` with all database and table structures
- **💬 Multi-Session Chat** — Create, switch, and delete multiple conversations
- **🌐 Bilingual UI** — Full Chinese and English interface support
- **⚙️ Persistent Configuration** — Settings auto-saved, no reconfiguration needed after restart
- **🎨 Modern UI** — Clean white theme built with React + TypeScript

### 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│          React + TypeScript + Vite           │
│                :5173                         │
├─────────────────────────────────────────────┤
│                  Backend                     │
│            FastAPI + Uvicorn                 │
│                :8000                         │
├──────────┬──────────┬───────────────────────┤
│  Agent   │LLM Client│    DB Client          │
│(Orchestr)│(Ollama/API)│(PostgreSQL/MySQL)    │
├──────────┴──────────┴───────────────────────┤
│      Skill Manager   │  Data Importer       │
│   (Metadata Mgmt)    │ (File Parse+Import)  │
└─────────────────────────────────────────────┘
```

### 📁 Project Structure

```
sql_agent/
├── server.py              # FastAPI backend server
├── agent.py               # Core agent logic (orchestrates LLM + DB)
├── llm_client.py          # LLM client (Ollama / OpenAI API)
├── db_client.py           # Database client (multi-DB support)
├── prompts.py             # LLM prompt templates
├── skill_manager.py       # skill.md metadata manager
├── file_parser.py         # File parser (Excel/CSV/Parquet/JSON/PKL)
├── data_importer.py       # Data importer (column matching + batch insert)
├── conversation_store.py  # Conversation persistence
├── config.py              # Configuration
├── main.py                # CLI mode entry point
├── requirements.txt       # Python dependencies
├── skill.md               # Database metadata (auto-maintained)
└── frontend/              # React frontend
    ├── src/
    │   ├── App.tsx         # Root component
    │   ├── api.ts          # API client
    │   ├── i18n.ts         # Internationalization (zh/en)
    │   ├── types.ts        # TypeScript type definitions
    │   └── components/
    │       ├── ChatArea.tsx       # Chat area (with file upload)
    │       ├── Sidebar.tsx        # Sidebar (session management)
    │       ├── SetupWizard.tsx    # Setup wizard
    │       ├── MessageBubble.tsx  # Message bubble
    │       └── ContextMenu.tsx    # Context menu
    └── package.json
```

### 🚀 Quick Start

#### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL / MySQL / Oracle (any one)
- [Ollama](https://ollama.ai/) (if using local models)

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
python server.py
```

#### 5. Start the frontend

```bash
cd frontend
npm run dev
```

#### 6. Open in browser

Visit [http://localhost:5173](http://localhost:5173) and follow the setup wizard.

### 📎 File Import

Supported file formats for data import:

| Format | Extension |
|--------|-----------|
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Parquet | `.parquet` |
| JSON | `.json` |
| Pickle | `.pkl` |

**Import Rules:**
- Auto-increment fields (e.g., `id`) are skipped — generated by the database
- NOT NULL fields must have matching columns in the file, otherwise an error is raised
- Nullable fields missing from the file are filled with `NULL`
- Extra columns in the file (not in the table) are silently ignored

### ⚙️ Configuration

The setup wizard guides you through:

| Setting | Description |
|---------|-------------|
| Language | Chinese / English |
| Model Source | Local Ollama or API |
| Model Name | e.g., `gemma4:31b`, `gpt-4o` |
| Database Type | PostgreSQL / MySQL / Oracle |
| Connection | Host, port, username, password |

Settings are saved to `setup_config.json` and auto-loaded on restart.

---

<div align="center">

### 📄 License

MIT License

</div>
