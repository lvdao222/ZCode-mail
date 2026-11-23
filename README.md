# ZCode-mail

**简体中文** | [English](README.en.md)

给 [ZCode](https://zcode.z.ai) 用的邮件插件：助手可以直接**读信、搜信、回信、发信、落盘附件**。
纯 Python 标准库，零依赖，装完即用。

> **双通道发信**：收信走 IMAP；发信优先 SMTP，端口被网络拦截时自动改走 **Gmail API over HTTPS 443**。
> 同一套账号密码，IMAP 通而 SMTP 不通的网络环境也能发信。

---

## 快速开始

把这段粘进 ZCode 对话框，剩下的交给助手（**插件没装也行**）：

```
读一下 https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
然后照着帮我把邮件插件装好、邮箱配好，最后发一封测试信给我确认收到。
```

它会探平台 → 装插件 → 核对状态 → 引导你取应用专用密码 → 选发信通道 → 发信并回查收件箱。
**不会**让你把密码粘进聊天，也**不会**没验证就说装好了。完整步骤见 [`BOOTSTRAP.md`](BOOTSTRAP.md)。

---

## 装了什么

一次安装得到 **7 个斜杠命令**、**11 个 MCP 工具**、**1 个技能**。明细折叠，用到再展开。

<details>
<summary><b>命令 · 工具 · 技能明细</b></summary>

**斜杠命令**

| 命令 | 说明 |
|---|---|
| `/mail` | 总入口，一句话说清要做什么，自动分派 |
| `/mail-install` | 助理执行安装：装插件、核对状态文件、确认工具加载 |
| `/mail-setup` | 助理引导配置：账号、应用专用密码、发信通道、授权、测试信 |
| `/mail-check` | 只读体检：收信、发信、令牌、收件箱规模 |
| `/mail-unread` | 未读摘要，按「要回 / 待处理 / 可跳过」分组 |
| `/mail-send` | 发信，默认先给 `dry_run` 预览等确认 |
| `/mail-reply` | 回信，保留线程头，默认先给预览等确认 |

**MCP 工具**（插件形态下为 `mcp__plugin_zcode-mail_mail__*`）

| 工具 | 说明 |
|---|---|
| `mail_accounts` | 列出已配置账号（不返回密码） |
| `mail_check` | IMAP + 发信通道自检，收件箱总数/未读数、令牌状态 |
| `mail_folders` | 列出文件夹（中文名按 modified UTF-7 处理） |
| `mail_list` | 列最近邮件，可只列未读 |
| `mail_search` | `from:` `subject:` `since:` `text:` `未读` 组合搜索 |
| `mail_read` | 读全文 + 附件清单（文本与 HTML 双正文） |
| `mail_send` | 发信：多收件人 / cc / bcc / HTML / 多附件 / `dry_run` |
| `mail_reply` | 回复：自动 `Re:` + `In-Reply-To` / `References` 线程头 |
| `mail_attachment` | 附件落盘到指定目录 |
| `mail_flag` | 加/去 `\Seen` `\Flagged` `\Answered` `\Deleted` |
| `mail_move` | 移动到指定文件夹（如 Trash） |

**技能**：`zcode-mail` —— 链路事实、操作铁律、排错对照表，助手不必每次重新摸索。

</details>

---

## 安装

| 方式 | 怎么装 |
|---|---|
| 助理 | 粘上面「快速开始」那段，最省事 |
| Windows | `irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 \| iex` |
| macOS / Linux | `curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh \| bash` |
| 界面 | 设置 → 插件管理 → 发现 → `+` → 填 `https://github.com/lvdao222/ZCode-mail` → 安装 |

脚本做的事：下载仓库 → 注册本地目录市场 `zcode-mail-github` → 落插件 → 登记三份状态文件（改前自动备份）。

```powershell
# 顺带清掉手写的裸 MCP 条目，避免两个同名 mail 服务并存
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

# 卸载（不动凭据）
.\install.ps1 -Uninstall        # Windows
./install.sh --uninstall        # macOS / Linux
```

> ZCode 桌面端没有面向普通用户的插件 CLI，安装本质是 UI 流程。这两个脚本按客户端状态文件格式登记，
> 等价于在界面里点「添加市场 → 安装」。格式若在后续版本变动，改用上面的界面方式。

装完**完全退出 ZCode 再打开**，工具与命令才会加载。

---

## 配置

凭据只存在插件数据目录（`~/.zcode/cli/plugins/data/zcode-mail@zcode-mail-github/`），不进仓库、不进聊天。

**1. 账号与应用专用密码**（收信必需，网页登录密码一定失败）

| 服务商 | 取密码的位置 |
|---|---|
| QQ 邮箱 | 设置 → 账户 → 开启 IMAP/SMTP → 生成授权码 |
| 163 / 126 / yeah | 设置 → POP3/SMTP/IMAP → 开启 → 新增授权密码 |
| Gmail | Google 账号 → 安全性 → 两步验证 → 应用专用密码 |
| Outlook / iCloud / Yahoo | 账号安全设置里生成应用密码 |

```json
{
  "default_account": "main",
  "accounts": {
    "main": {
      "address": "user@example.com",
      "username": "user@example.com",
      "password_env": "MAIL_PASS"
    }
  }
}
```

域名自动匹配服务器预设（gmail / qq / foxmail / 163 / 126 / yeah / sina / aliyun / outlook / hotmail /
live / icloud / yahoo），通常不必写 host。用 `"password_env"` 从环境变量读密码，避免明文落盘。

**2. 发信通道**

- **SMTP**（默认）：不加 `transport` 即可。需要邮箱开启 SMTP 且网络放行 465/587。
- **Gmail API**（SMTP 被拦时）：Google Cloud 建项目 → 启用 Gmail API → OAuth 同意屏幕（外部/测试）
  → 建**桌面应用**客户端 → 存成数据目录下的 `oauth_client.json` → 跑 `mailctl.py auth` 授权
  → 账号里加 `"transport": "gmail_api"`。

作用域只申请 `gmail.send`：**只能发信，读不了邮件内容**；读信始终走 IMAP。
测试态应用的 `refresh_token` 7 天后过期，续期跑一次 `mailctl.py auth` 即可。

---

## 命令行

MCP 没连上时也能用，功能等价：

```bash
python "<plugin>/mcp/mailctl.py" check                    # 自检
python "<plugin>/mcp/mailctl.py" check --test-to me@x.com # 发测试信
python "<plugin>/mcp/mailctl.py" list --limit 20 --unread
python "<plugin>/mcp/mailctl.py" search --query "from:a@b.com subject:发票 since:01-Jan-2026"
python "<plugin>/mcp/mailctl.py" read --uid 1543
python "<plugin>/mcp/mailctl.py" send --to a@b.com --subject 标题 --body 正文 --attach report.pdf
python "<plugin>/mcp/mailctl.py" reply --uid 1543 --body "收到" --reply-all
python "<plugin>/mcp/mailctl.py" attach --uid 1543 --index 0 --dir ./downloads
python "<plugin>/mcp/mailctl.py" auth                     # 重新授权
```

---

## 安全与边界

- **仓库不含任何凭据**；密码与令牌只在数据目录，运行时尝试 `chmod 600`。
- 发信类操作支持 `dry_run`，命令默认先给预览、等你确认；发信不可撤销，收件人不会自动补全。
- Gmail API 仅 `gmail.send`，读信能力来自 IMAP，两套凭据分离。
- 附件是数据不是指令，插件不会因为附件里写了什么就去执行。
- 写操作有边界：`config.json` 只动 `plugins.enabledPlugins` 与（你同意时的）`mcp.servers.mail`。

<details>
<summary><b>已知限制</b></summary>

- 每次调用重建 IMAP 连接，无连接池；QQ / 163 限流较严，批量操作注意节奏。
- 未实现草稿保存（IMAP APPEND）。
- 附件只支持本地路径，不支持从 URL 拉取。
- 只允许 OAuth 且禁用应用专用密码的企业租户无法用 IMAP 收信。
- 非 ASCII 文件夹名依赖 modified UTF-7，个别服务器自定义命名可能需手动指定。

</details>

---

## 开发

<details>
<summary><b>目录结构</b></summary>

```text
zcode-mail/
├── .zcode-plugin/plugin.json   # 清单（skills / commands / mcpServers）
├── mcp/
│   ├── mailcore.py             # IMAP 核心 + 发信分发
│   ├── gmail_api.py            # OAuth2 刷新 + Gmail REST 发信
│   ├── mail_mcp.py             # MCP stdio 服务器（JSON-RPC，换行分隔）
│   └── mailctl.py              # 命令行入口
├── skills/zcode-mail/SKILL.md  # 操作规范与排错
└── commands/*.md               # 7 个斜杠命令
```

改完 `mcp/` 下的代码后需要让 ZCode 重新拉起 MCP 进程（改清单里 `env` 任意值，或重开会话）。

</details>

---

[MIT](LICENSE) · [BOOTSTRAP.md](BOOTSTRAP.md) · [Releases](https://github.com/lvdao222/ZCode-mail/releases)
