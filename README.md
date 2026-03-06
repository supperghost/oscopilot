# Linux OS Copilot Agent (MVP)

本项目提供一个可安装的 Python 包与 CLI：`oscopilot`，用于在 Linux 系统上安全运行 OS Copilot Agent 的最小可用版本（MVP）。

> 目标场景：常见问题排查（CPU/内存/磁盘/网络/进程/服务 systemd/日志）、工具与软件部署（apt/yum/dnf）、健康巡检与报告生成，默认支持 Ubuntu/Debian 与 RHEL/CentOS 系。

## 工程结构

```text
os-copilot-agent/
  pyproject.toml          # Python 包配置，提供 oscopilot CLI
  oscopilot/
    __init__.py
    utils.py              # 输入净化（零宽字符防御）、ID 生成
    config.py             # YAML 配置加载与数据类
    auditing.py           # JSON Lines 审计日志 + 简易 metrics
    policy.py             # 策略引擎（白/黑名单、参数约束、速率限制）
    approval.py           # 人机审批（交互 / 队列 + dry-run）
    context.py            # AppContext 聚合配置、策略、审计、审批
    tools/
      __init__.py
      system_info.py      # 安全的 CPU 负载 & 前 5 进程查询
      files.py            # 文件查看 & 带 Diff 的安全追加写入
      systemd_tools.py    # systemd status/start/stop/restart（审批+策略）
      package_manager.py  # apt/yum/dnf 查询与安装（审批+策略）
      mcp_client.py       # JSON-RPC over stdio MCP 客户端
    agent_langchain.py    # LangChain Agent，把工具注册给 LLM
    cli.py                # Typer CLI，实现 oscopilot … 子命令
  examples/
    config.example.yaml   # 配置模板
    audit_example.jsonl   # 示例审计日志片段
  oscopilot.service       # systemd unit 示例（用户服务推荐）
  README.md
```

## 安装与运行

### 环境要求

- Python 3.10+
- Linux（推荐 Ubuntu/Debian 或 RHEL/CentOS 系）
- 能访问 OpenAI 兼容 LLM 接口（或本地代理）

### 安装

```bash
cd os-copilot-agent
pip install .
# 或开发模式
pip install -e .
```

安装完成后将获得 `oscopilot` CLI：

```bash
oscopilot --help
```

### 配置

1. 复制示例配置：

```bash
sudo mkdir -p /etc/oscopilot
sudo cp examples/config.example.yaml /etc/oscopilot/config.yaml
sudo chmod 600 /etc/oscopilot/config.yaml
```

2. 根据实际情况修改 `/etc/oscopilot/config.yaml`：

- `llm`: 配置 LLM base_url/token/model（OpenAI 兼容接口）
- `policy.whitelist_commands`: 允许的 systemd / 包管理命令别名
- `policy.blacklist_patterns`: 高危模式（如 `rm -rf /`）
- `approval`: 审批模式（默认 `interactive`）与 dry-run 开关
- `mcp.servers.sysom_mcp`: 配置 SysOM MCP 的启动命令和工作目录
- `tools.allowed_write_tools`: 允许的变更工具（默认只包含 `append_hosts_mapping`）

日志与审计默认路径：

```yaml
audit:
  log_path: "./logs/oscopilot.log"
  audit_path: "./logs/audit.jsonl"
  metrics_path: "./logs/metrics.json"
```

可根据需要指向 `/var/log/oscopilot/…`。

### systemd 服务示例

`oscopilot.service` 为用户服务示例（推荐）：

```ini
[Unit]
Description=Oscopilot Linux OS Copilot Agent
After=network.target

[Service]
Type=simple
# 建议以用户服务运行，将本 unit 放在 ~/.config/systemd/user/oscopilot.service
ExecStart=/usr/bin/env oscopilot agent run --config /etc/oscopilot/config.yaml
WorkingDirectory=/etc/oscopilot
Restart=on-failure

[Install]
WantedBy=default.target
```

使用步骤（以用户服务为例）：

```bash
mkdir -p ~/.config/systemd/user
cp oscopilot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oscopilot.service
```

## CLI 子命令

### 1. Agent：`oscopilot agent run`

启动 LangChain Agent，读取配置，注册安全工具并绑定 LLM：

```bash
# 交互模式
oscopilot agent run --config /etc/oscopilot/config.yaml

# 一次性指令
oscopilot agent run --config /etc/oscopilot/config.yaml \
  --once "检查 CPU 负载并列出前 5 个高 CPU 进程"
```

Agent 内注册的关键工具：

- `check_cpu_and_top_processes`：使用 `psutil` 查询 CPU load + 前 5 进程
- `append_hosts_mapping`：封装 `/etc/hosts` 追加行为
  - 调用前由策略引擎检查
  - 调用时由审批模块展示 Diff + 中文提示并请求确认
  - 审计日志记录 `file_diff_hash`（diff 的 SHA256）

### 2. MCP：`oscopilot mcp exec <tool> <json>`

通过 MCP 客户端（JSON-RPC over stdio）调用如 SysOM MCP 的诊断工具：

```bash
oscopilot mcp exec sysom_mcp sysom.load_diagnose "{\"target\":\"system\"}"
```

行为：

- 从配置 `mcp.servers.sysom_mcp` 读取 `command/args/env/cwd`
- 通过 `--stdio` 启动 MCP 服务器
- 写入 JSON-RPC 请求并读取响应
- 返回结构化结果（以 JSON 打印）
- 记录审计事件 `tool="mcp:<tool>"`，stdout 保存结果 JSON

### 3. 审批队列：`oscopilot approve queue`

当 `approval.mode: queue` 时，高风险操作不会立即执行，而是进入队列文件（例如 `./logs/approval_queue.jsonl`），等待集中审批：

```bash
oscopilot approve queue --config /etc/oscopilot/config.yaml
# 或限制本次审批条数
oscopilot approve queue --config /etc/oscopilot/config.yaml --limit 5
```

行为：

- 逐条读取 `pending` 记录
- 展示操作类型、参数以及（如有）Diff 预览
- 中文提示语：`即将执行如下高风险操作，请仔细检查 Diff 并确认：`
- 对 `file_write` 类型操作，审批通过后真正写盘
- 每条记录在审计日志中写入对应 `approval_result`

### 4. 策略测试：`oscopilot policy test <json>`

快速验证策略引擎对某个操作的判定：

```bash
oscopilot policy test '{"type":"shell","name":"systemctl_start","args":{"unit":"nginx.service"}}'
```

返回示例：

```json
{
  "allowed": true,
  "requires_approval": true,
  "reason": "允许"
}
```

### 5. 审计报告：`oscopilot report last`

查看最近一次 session 的审计摘要：

```bash
oscopilot report last --config /etc/oscopilot/config.yaml
```

输出示例：

```json
{
  "session_id": "...",
  "event_count": 3,
  "tools": {
    "psutil_cpu": 1,
    "append_line": 2
  },
  "last_event": { "...": "..." }
}
```

### 6. Demo：编辑 /etc/hosts（带 Diff + 审批）

为保证可重复自测，提供一个直接的演示命令：

```bash
sudo oscopilot demo-hosts 127.0.0.1 example.local \
  --config /etc/oscopilot/config.yaml
```

流程：

1. 读取 `/etc/hosts` 当前内容
2. 计算追加行后的新内容
3. 生成统一 Diff：`files.append_line_with_approval` 中通过 `difflib.unified_diff` 实现
4. 计算 `file_diff_hash = sha256(diff)`
5. 调用审批模块：展示 Diff 与中文提示，要求键入 `y/yes` 才执行
6. 审批通过时写盘，并将 `file_diff_hash` 写入审计日志

当 `approval.mode = queue` 时，该操作不会立即写盘，而是进入队列，需通过 `oscopilot approve queue` 统一审批。

## 安全与策略落地要点

1. **严禁 auto-approve/YOLO 模式**
   - 不提供任何自动批准开关
   - 高风险操作（文件写入、systemd 启停、包安装）一律走策略 + 审批

2. **文件写入必须 Diff 预览 + 审批 + 审计**
   - `files.append_line_with_approval`：生成统一 Diff、计算哈希
   - 审批提示中展示 Diff
   - 审计日志字段 `file_diff_hash` 写入 Diff 哈希

3. **输入净化与参数校验**
   - `utils.ensure_no_invisible` 检查零宽等不可见字符（防止隐形提示词注入）
   - CLI 中对 `tool`、`params_json`、`operation_json` 等用户输入统一做净化
   - `policy.parameter_regex` 对关键参数（如包名）做正则约束

4. **最小权限与变更工具显式开启**
   - 默认不使用 `sudo`（`tools.use_sudo: false`），避免直接以 root 运行
   - 推荐将 `oscopilot` 部署为用户级 systemd 服务
   - 仅查询类工具默认可用；变更类工具需要在 `tools.allowed_write_tools` 中显式列出

5. **策略引擎**
   - 白名单：只允许配置中声明的命令别名（如 `systemctl_start`、`pkg_install`）
   - 黑名单：拒绝高危模式（如 `rm -rf /`、fork bomb 等）
   - 参数正则：限制包名、服务名、主机名等
   - 速率限制：`max_operations_per_minute` 控制工具调用频率

6. **可观测性**
   - 日志：`auditing.AuditLogger` 将运行日志写入 `log_path`
   - 审计：所有工具调用与审批结果写入 `audit_path`（JSON Lines）
   - 度量：计数器写入 `metrics_path`（JSON），按工具名统计调用次数
   - 追踪：`session_id` 与 `action_id` 贯穿审计记录

## 验收示例（自测建议）

### 示例一：CPU 负载与前 5 个高 CPU 进程

1. 启动 Agent：

```bash
oscopilot agent run --config /etc/oscopilot/config.yaml
```

2. 在对话中输入：

> "请帮我检查当前 CPU 负载，并列出前 5 个高 CPU 进程，顺便解释一下结果。"

3. 期望行为：
   - Agent 调用 `check_cpu_and_top_processes` 工具
   - 输出 CPU load(1/5/15) 与前 5 进程的 PID/CPU/用户名/名称
   - Agent 用中文解释负载与进程含义
   - 审计日志中有一条对应的 `psutil_cpu` 事件

### 示例二：编辑 /etc/hosts 追加一条映射

> 注意：需要确保当前用户具有写入 `/etc/hosts` 的权限，通常需通过 `sudo`。

```bash
sudo oscopilot demo-hosts 127.0.0.1 example.local \
  --config /etc/oscopilot/config.yaml
```

期望行为：

1. 终端展示 `/etc/hosts` 的 Diff 预览（新增行 `127.0.0.1 example.local`）
2. 终端提示中文审批文案：`即将执行如下高风险操作，请仔细检查 Diff 并确认：...`
3. 用户输入 `y` 才继续；否则操作被拒绝并记入审计
4. 审批通过：
   - `/etc/hosts` 落盘
   - 审计日志中有一条 `append_line` 记录，字段 `file_diff_hash` 为 Diff 的 SHA256

### 示例三：通过 SysOM MCP 执行诊断

假设已按文档部署 `sysom_mcp` 并在配置中配置 `mcp.servers.sysom_mcp`：

```bash
oscopilot mcp exec sysom_mcp sysom.load_diagnose "{\"target\":\"system\"}"
```

期望行为：

- CLI 启动 `uv run python sysom_main_mcp.py --stdio`
- 通过 JSON-RPC 发送请求并读取响应
- 打印结构化诊断结果（例如内存/负载/IO 分析）
- 审计日志中记录 `tool="mcp:sysom.load_diagnose"` 的事件

## 多机扩展（占位）

当前 MVP 聚焦单机；多主机场景可通过后续扩展：

- 在配置中增加 SSH 目标定义
- 使用 Paramiko / OpenSSH 执行远程命令，并在本地统一审计
- 或在每台机器上部署本 Agent，通过集中式 LLM 与审批服务进行编排

## 容器化与隔离（占位说明）

为进一步提升安全性，可在后续版本中引入：

- 将变更类操作封装在容器中执行（例如使用 rootless Podman）
- 通过挂载只读/只写路径控制最小文件访问范围
- 利用 seccomp/cgroup 限制子进程能力

> 本 MVP 以最小可用实现为目标，重点落地配置化策略、审批与审计闭环，为后续容器化隔离留出明确的扩展点。
