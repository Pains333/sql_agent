"""
SQL Agent CLI 入口
美化的命令行交互界面
"""

import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.text import Text
from rich import box

from backend.core.agent import SQLAgent
from backend.core.logging_config import setup_logging

console = Console()


def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════╗
║          🤖 智能数据库助手 - PostgreSQL               ║
║          Powered by Ollama gemma4:31b                ║
╠══════════════════════════════════════════════════════╣
║  用语言描述你的需求，AI 帮你操作数据库            ║
║                                                      ║
║  示例:                                               ║
║    "帮我创建一个用户表，有姓名和邮箱"                 ║
║    "查看用户表的所有数据"                             ║
║    "给用户表加一个手机号字段"                         ║
║                                                      ║
║  命令: \\q 退出 | \\skill 查看表结构                   ║
║        \\db 查看数据库 | \\help 帮助                   ║
╚══════════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


def print_sql(sql: str):
    """高亮显示 SQL 语句"""
    if sql:
        syntax = Syntax(sql, "sql", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="📝 SQL", border_style="blue", box=box.ROUNDED))


def print_result_table(columns: list, rows: list):
    """以表格形式展示查询结果"""
    if not columns:
        console.print("[yellow]查询无结果[/yellow]")
        return

    table = Table(
        show_header=True,
        header_style="bold magenta",
        border_style="bright_blue",
        box=box.ROUNDED,
        title="📊 查询结果",
        title_style="bold white",
    )

    for col in columns:
        table.add_column(str(col))

    for row in rows:
        table.add_row(*[str(v) if v is not None else "NULL" for v in row])

    console.print(table)
    console.print(f"[dim]共 {len(rows)} 条记录[/dim]")


def print_explanation(explanation: str):
    """显示解释说明"""
    if explanation:
        console.print(Panel(
            explanation,
            title="💡 说明",
            border_style="green",
            box=box.ROUNDED,
        ))


def print_error(error: str):
    """显示错误信息"""
    console.print(Panel(
        error,
        title="❌ 错误",
        border_style="red",
        box=box.ROUNDED,
    ))


def print_success(message: str):
    """显示成功信息"""
    console.print(f"[bold green]✅ {message}[/bold green]")


def confirm_ddl(action: str, sql: str, explanation: str, is_dangerous: bool) -> bool:
    """
    DDL 操作确认回调

    Args:
        action: 操作类型
        sql: SQL 语句
        explanation: 操作说明
        is_dangerous: 是否是危险操作

    Returns:
        是否确认执行
    """
    console.print()
    if is_dangerous:
        style = "bold red"
        title = "⚠️  危险操作确认"
        console.print(Panel(
            f"[red]{explanation}[/red]",
            title=title,
            border_style="red",
            box=box.DOUBLE,
        ))
    else:
        style = "bold yellow"
        title = "📋 操作确认"
        console.print(Panel(
            explanation,
            title=title,
            border_style="yellow",
            box=box.ROUNDED,
        ))

    print_sql(sql)
    return Confirm.ask(f"[{style}]确认执行此操作?[/{style}]", default=False)


def handle_special_command(command: str, agent: SQLAgent) -> bool:
    """
    处理特殊命令

    Args:
        command: 命令字符串
        agent: Agent 实例

    Returns:
        True 如果是特殊命令并已处理
    """
    cmd = command.strip().lower()

    if cmd in ("\\q", "exit", "quit"):
        console.print("[bold cyan]👋 再见！[/bold cyan]")
        agent.close()
        sys.exit(0)

    elif cmd == "\\skill":
        skill_content = agent.skill.read()
        console.print(Panel(
            Markdown(skill_content),
            title="📄 skill.md - 数据库元信息",
            border_style="cyan",
            box=box.ROUNDED,
        ))
        return True

    elif cmd == "\\db":
        db_name = agent.get_current_db()
        console.print(f"[bold cyan]📍 当前数据库: [white]{db_name}[/white][/bold cyan]")
        # 列出所有数据库
        try:
            databases = agent.db.list_databases()
            table = Table(
                title="所有数据库",
                show_header=True,
                header_style="bold magenta",
                box=box.ROUNDED,
            )
            table.add_column("数据库名", style="cyan")
            table.add_column("状态")
            for db in databases:
                status = "◀ 当前" if db == db_name else ""
                table.add_row(db, f"[green]{status}[/green]")
            console.print(table)
        except Exception as e:
            print_error(str(e))
        return True

    elif cmd.startswith("\\use "):
        db_name = command.strip()[5:].strip()
        if not db_name:
            console.print("[yellow]用法: \\use <数据库名>[/yellow]")
        else:
            result = agent.switch_database(db_name)
            if "失败" in result:
                print_error(result)
            else:
                print_success(result)
        return True

    elif cmd == "\\clear":
        agent.llm.reset_history()
        console.print("[bold cyan]🔄 对话历史已清除[/bold cyan]")
        return True

    elif cmd == "\\help":
        help_text = """
**可用命令:**

| 命令 | 说明 |
|------|------|
| `\\q` / `exit` | 退出程序 |
| `\\skill` | 查看数据库元信息 (skill.md) |
| `\\db` | 查看当前数据库和所有数据库列表 |
| `\\use <name>` | 切换到指定数据库 |
| `\\clear` | 清除对话历史 |
| `\\help` | 显示此帮助 |

**使用方式:**
直接用中文描述你想要的操作，AI 会自动生成并执行 SQL。

**示例:**
- "帮我创建一个用户信息表，字段有用户id，性别，邮箱"
- "创建一个名为 mydb 的数据库"
- "往用户表里添加一条数据，张三，男，zhangsan@email.com"
- "查看用户表里的所有数据"
- "给用户表加一个手机号字段"
- "删除用户表中邮箱为空的记录"
"""
        console.print(Panel(
            Markdown(help_text),
            title="📖 帮助",
            border_style="cyan",
            box=box.ROUNDED,
        ))
        return True

    return False


def main():
    """主函数 - CLI 交互循环"""
    setup_logging()
    print_banner()

    # 初始化 Agent
    try:
        agent = SQLAgent()
        console.print(f"[green]✅ 已连接到 PostgreSQL (数据库: {agent.get_current_db()})[/green]")
        console.print(f"[green]✅ AI 模型: gemma4:31b[/green]")
        console.print(f"[dim]💬 直接输入中文描述你的需求，例如：帮我创建一个用户信息表[/dim]")
        console.print()
    except Exception as e:
        print_error(f"初始化失败: {e}")
        sys.exit(1)

    while True:
        try:
            # 显示提示符
            db_name = agent.get_current_db()
            user_input = Prompt.ask(
                f"[bold cyan]{db_name}[/bold cyan] [bold white]>[/bold white]"
            )

            if not user_input.strip():
                continue

            # 检查是否是特殊命令
            if handle_special_command(user_input, agent):
                continue

            # 第一阶段：LLM 思考（在 spinner 中）
            with console.status("[bold cyan]🤔 思考中...[/bold cyan]", spinner="dots"):
                plan = agent.think(user_input)

            # 第二阶段：确认 + 执行（在 spinner 外，允许交互式输入）
            result = agent.execute_plan(plan, confirm_callback=confirm_ddl)

            # 显示结果
            if result["error"]:
                print_error(result["error"])
                continue

            # 显示 SQL
            if result["sql"]:
                print_sql(result["sql"])

            # 显示解释
            if result["explanation"] and result["action"] != "chat":
                print_explanation(result["explanation"])

            # 显示执行结果
            if result["success"]:
                res = result["result"]

                if result["action"] == "chat":
                    # 纯对话
                    console.print(Panel(
                        str(res),
                        title="🤖 回复",
                        border_style="green",
                        box=box.ROUNDED,
                    ))

                elif isinstance(res, tuple) and len(res) == 2:
                    # 查询结果 (columns, rows)
                    columns, rows = res
                    print_result_table(columns, rows)

                elif isinstance(res, str):
                    print_success(res)

            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]👋 再见！[/bold cyan]")
            agent.close()
            sys.exit(0)


if __name__ == "__main__":
    main()
