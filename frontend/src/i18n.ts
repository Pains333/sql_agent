
export type Lang = 'zh' | 'en';

const texts = {
  // Setup Wizard
  'setup.title': { zh: '初始配置', en: 'Initial Setup' },
  'setup.step': { zh: '步骤', en: 'Step' },
  'setup.prev': { zh: '上一步', en: 'Previous' },
  'setup.next': { zh: '下一步', en: 'Next' },
  'setup.finish': { zh: '完成', en: 'Finish' },
  'setup.connecting': { zh: '正在连接并扫描数据库...', en: 'Connecting & scanning database...' },

  // Step 1
  'step1.title': { zh: '语言设置', en: 'Language' },
  'step1.desc': { zh: '选择界面语言', en: 'Select interface language' },
  'step1.label': { zh: '语言', en: 'Language' },
  'step1.zh': { zh: '中文', en: 'Chinese' },
  'step1.en': { zh: 'English', en: 'English' },

  // Step 2
  'step2.title': { zh: '模型配置', en: 'Model Configuration' },
  'step2.desc': { zh: '选择 AI 模型来源', en: 'Choose your AI model source' },
  'step2.type': { zh: '模型来源', en: 'Model Source' },
  'step2.local': { zh: '本地模型', en: 'Local Model' },
  'step2.api': { zh: '第三方模型', en: 'Third-party Model' },
  'step2.localHint': { zh: '本地模型只支持 Ollama', en: 'Local models only support Ollama' },
  'step2.model': { zh: '选择模型', en: 'Select Model' },
  'step2.noModels': { zh: '未检测到本地模型', en: 'No local models detected' },
  'step2.loading': { zh: '加载中...', en: 'Loading...' },
  'step2.apiUrl': { zh: 'API 地址', en: 'API Base URL' },
  'step2.apiUrlPlaceholder': { zh: '例如: https://api.openai.com', en: 'e.g. https://api.openai.com' },
  'step2.apiKey': { zh: 'API Key', en: 'API Key' },
  'step2.apiKeyPlaceholder': { zh: '输入你的 API Key', en: 'Enter your API Key' },
  'step2.apiModel': { zh: '模型名称', en: 'Model Name' },
  'step2.apiModelPlaceholder': { zh: '例如: gpt-4o', en: 'e.g. gpt-4o' },

  // Step 3
  'step3.title': { zh: '数据库配置', en: 'Database Configuration' },
  'step3.desc': { zh: '配置数据库连接信息', en: 'Configure database connection' },
  'step3.type': { zh: '数据库类型', en: 'Database Type' },
  'step3.host': { zh: '数据库地址', en: 'Database Host' },
  'step3.port': { zh: '数据库端口', en: 'Database Port' },
  'step3.user': { zh: '数据库用户名', en: 'Database Username' },
  'step3.userPlaceholder': { zh: '输入数据库用户名', en: 'Enter database username' },
  'step3.password': { zh: '数据库密码', en: 'Password' },
  'step3.passwordPlaceholder': { zh: '输入数据库密码', en: 'Enter database password' },
  'step3.dbFilePath': { zh: '数据库文件路径', en: 'Database File Path' },
  'step3.dbFilePathPlaceholder': { zh: '输入 .sqlite, .db, 或 .duckdb 文件路径', en: 'Enter path to .sqlite, .db, or .duckdb file' },

  // Chat
  'chat.title': { zh: '智能数据库助手', en: 'Smart Database Assistant' },
  'chat.subtitle': { zh: '用自然语言描述你的需求，AI 帮你操作数据库', en: 'Describe your needs in natural language, AI helps you operate the database' },
  'chat.placeholder': { zh: '描述你的数据库操作需求...', en: 'Describe your database operation...' },
  'chat.placeholderWithFile': { zh: '描述如何处理附件数据，如: 将附件数据导入到 users 表...', en: 'Describe how to handle the attachment, e.g.: Import attachment data into users table...' },
  'chat.send': { zh: '发送', en: 'Send' },
  'chat.inputHint': { zh: '按 Enter 发送，Shift + Enter 换行，输入 / 查看命令', en: 'Enter to send, Shift+Enter for newline, type / for commands' },
  'chat.welcome': { zh: '输入你的需求，开始对话', en: 'Type your request to start' },
  'chat.example1': { zh: '帮我创建一个用户信息表', en: 'Create a user information table' },
  'chat.example2': { zh: '查看所有表的数据', en: 'Show all table data' },
  'chat.example3': { zh: '给用户表加一个手机号字段', en: 'Add a phone field to users table' },
  'chat.uploading': { zh: '上传中...', en: 'Uploading...' },
  'chat.uploadTitle': { zh: '上传附件 (Excel, CSV, PKL, Parquet, JSON)', en: 'Upload file (Excel, CSV, PKL, Parquet, JSON)' },
  'chat.removeAttachment': { zh: '移除附件', en: 'Remove attachment' },
  'chat.columns': { zh: '列', en: 'cols' },
  'chat.rows': { zh: '行', en: 'rows' },

  // Sidebar
  'sidebar.newChat': { zh: '新建对话', en: 'New Chat' },
  'sidebar.empty': { zh: '暂无对话，点击上方 ＋ 开始', en: 'No chats yet, click + to start' },
  'sidebar.delete': { zh: '删除对话', en: 'Delete Chat' },
  'sidebar.reconfigure': { zh: '重新配置', en: 'Reconfigure' },
  'sidebar.justNow': { zh: '刚刚', en: 'Just now' },
  'sidebar.minutesAgo': { zh: '分钟前', en: 'min ago' },
  'sidebar.hoursAgo': { zh: '小时前', en: 'hr ago' },
  'sidebar.daysAgo': { zh: '天前', en: 'd ago' },
  'sidebar.collapse': { zh: '折叠侧栏', en: 'Collapse sidebar' },
  'sidebar.expand': { zh: '展开侧栏', en: 'Expand sidebar' },

  // Theme
  'theme.light': { zh: '浅色模式', en: 'Light Mode' },
  'theme.dark': { zh: '深色模式', en: 'Dark Mode' },

  // Database
  'db.current': { zh: '当前数据库', en: 'Current Database' },
  'db.switch': { zh: '切换数据库', en: 'Switch Database' },
  'db.switchSuccess': { zh: '已切换到数据库', en: 'Switched to database' },
  'db.switchFailed': { zh: '切换失败', en: 'Switch failed' },

  // Schema Browser
  'schema.title': { zh: '数据库结构', en: 'Schema Browser' },
  'schema.tables': { zh: '表', en: 'Tables' },
  'schema.columns': { zh: '列', en: 'Columns' },
  'schema.noTables': { zh: '暂无表', en: 'No tables' },
  'schema.loading': { zh: '加载中...', en: 'Loading...' },

  // SQL Edit / DDL Confirmation
  'sql.execute': { zh: '执行', en: 'Execute' },
  'sql.cancel': { zh: '取消', en: 'Cancel' },
  'sql.edit': { zh: '编辑 SQL', en: 'Edit SQL' },
  'sql.confirmDDL': { zh: '此操作将修改数据库结构，请确认', en: 'This will modify the database structure, please confirm' },
  'sql.confirmImport': { zh: '此操作将导入数据到表中，请确认', en: 'This will import data into the table, please confirm' },
  'sql.dangerWarning': { zh: '危险操作！此操作不可撤销', en: 'Dangerous operation! This cannot be undone' },
  'sql.cancelled': { zh: '操作已取消', en: 'Operation cancelled' },
  'sql.executing': { zh: '执行中...', en: 'Executing...' },

  // Export
  'export.csv': { zh: '导出 CSV', en: 'Export CSV' },

  // Connection Status
  'status.dbConnected': { zh: '数据库已连接', en: 'Database connected' },
  'status.dbDisconnected': { zh: '数据库未连接', en: 'Database disconnected' },
  'status.llmConnected': { zh: '模型已连接', en: 'Model connected' },
  'status.llmDisconnected': { zh: '模型未连接', en: 'Model disconnected' },

  // Commands
  'cmd.tables': { zh: '查看所有表', en: 'Show all tables' },
  'cmd.databases': { zh: '查看所有数据库', en: 'Show all databases' },
  'cmd.describe': { zh: '查看表结构', en: 'Describe table structure' },
  'cmd.clear': { zh: '清空当前对话', en: 'Clear current conversation' },

  // Pagination
  'pagination.prev': { zh: '上一页', en: 'Previous' },
  'pagination.next': { zh: '下一页', en: 'Next' },
  'pagination.page': { zh: '页', en: 'Page' },

  // Settings
  'settings.title': { zh: '设置', en: 'Settings' },
  'settings.darkMode': { zh: '深色模式', en: 'Dark Mode' },
  'settings.language': { zh: '语言', en: 'Language' },
  'settings.streaming': { zh: '流式输出', en: 'Streaming' },
  'settings.streamingDesc': { zh: '实时显示 AI 思考过程', en: 'Show AI thinking in real-time' },
  'settings.fontSize': { zh: '字体大小', en: 'Font Size' },
  'settings.fontSmall': { zh: '小', en: 'S' },
  'settings.fontMedium': { zh: '中', en: 'M' },
  'settings.fontLarge': { zh: '大', en: 'L' },
  'settings.exportChat': { zh: '导出当前对话', en: 'Export Chat' },
  'settings.exportDesc': { zh: '导出为 Markdown 文件', en: 'Export as Markdown' },
  'settings.clearAll': { zh: '清空所有对话', en: 'Clear All Chats' },
  'settings.clearAllConfirm': { zh: '确定要删除所有对话吗？此操作不可撤销。', en: 'Delete all conversations? This cannot be undone.' },
  'settings.clearAllDone': { zh: '已清空所有对话', en: 'All conversations cleared' },
  'settings.shortcuts': { zh: '快捷键', en: 'Shortcuts' },
  'settings.shortcutSend': { zh: 'Enter — 发送消息', en: 'Enter — Send message' },
  'settings.shortcutNewline': { zh: 'Shift + Enter — 换行', en: 'Shift + Enter — New line' },
  'settings.shortcutCommand': { zh: '/ — 快捷命令', en: '/ — Quick commands' },
  'settings.shortcutEsc': { zh: 'Esc — 关闭弹窗', en: 'Esc — Close popup' },
  'settings.about': { zh: '关于', en: 'About' },
  'settings.version': { zh: '版本', en: 'Version' },
  'settings.noActiveChat': { zh: '没有活跃对话可导出', en: 'No active chat to export' },
  'settings.confirm': { zh: '确认', en: 'Confirm' },
  'settings.cancelBtn': { zh: '取消', en: 'Cancel' },

  // Errors
  'error.title': { zh: '错误', en: 'Error' },
  'error.connectionFailed': { zh: '连接失败', en: 'Connection failed' },
  'error.dbUserRequired': { zh: '请输入数据库用户名', en: 'Database username is required' },
  'error.dbPasswordRequired': { zh: '请输入数据库密码', en: 'Database password is required' },
  'error.apiUrlRequired': { zh: '请输入 API 地址', en: 'API Base URL is required' },
  'error.apiKeyRequired': { zh: '请输入 API Key', en: 'API Key is required' },
  'error.apiModelRequired': { zh: '请输入模型名称', en: 'Model name is required' },
} as const;

type TextKey = keyof typeof texts;

let currentLang: Lang = 'zh';

export function setLang(lang: Lang) {
  currentLang = lang;
}

export function getLang(): Lang {
  return currentLang;
}

export function t(key: TextKey): string {
  const entry = texts[key];
  if (!entry) return key;
  return entry[currentLang] || entry['zh'] || key;
}
