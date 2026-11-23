# ZCode-mail

**简体中文** | [English](README.en.md)

给 [ZCode](https://zcode.z.ai) 用的邮件插件。装好之后，ZCode 里的助手可以直接**读信、搜信、回信、发信、落盘附件**。

纯 Python 标准库实现，**零第三方依赖**（不需要 `pip install` 任何东西）。

## 最懒的用法：一句话装完配好

把下面整段粘进 ZCode 对话框，剩下的交给助理（**连插件都还没装也行**）：

```
读一下 https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
然后照着帮我把邮件插件装好、邮箱配好，最后发一封测试信给我确认收到。
```

助理会自己探平台、跑安装、核对状态文件、引导你取应用专用密码、挑发信通道（SMTP 优先，
被拦则切 Gmail API 走 443）、发测试信并回查收件箱。它不会让你把密码贴进聊天，
也不会没验证就说装好了。细节见 [`BOOTSTRAP.md`](BOOTSTRAP.md)。

## 为什么不是简单的 SMTP

很多网络环境会对 SMTP 端口做拦截：`smtp.gmail.com:465` 的 TLS 握手长时间超时，`587` / `25` 连接被直接关闭，
但同一个账号密码走 `imap.gmail.com:993` 完全正常。这是端口级拦截，不是服务端拒绝。

所以本插件是**双通道**设计：

| 方向 | 通道 | 端点 | 凭据 |
|---|---|---|---|
| 收信 | IMAP over SSL | `imap.<域名>:993` | 应用专用密码 / 授权码 |
| 发信（推荐） | **Gmail API (HTTPS)** | `gmail.googleapis.com` | OAuth2 refresh_token |
| 发信（备选） | SMTP | `smtp.<域名>:465 / 587` | 应用专用密码 / 授权码 |

发信通道由 `accounts.json` 里的 `transport` 决定：`"gmail_api"` 走 HTTPS，缺省走 SMTP。

## 能力

**MCP 工具**（插件形态下为 `mcp__plugin_zcode-mail_mail__*`，裸挂 MCP 时为 `mcp__mail__*`）

| 工具 | 说明 |
|---|---|
| `mail_accounts` | 列出已配置账号（不返回密码） |
| `mail_check` | IMAP + 发信通道自检，返回收件箱总数/未读数、令牌状态 |
| `mail_folders` | 列出文件夹（中文名按 modified UTF-7 处理） |
| `mail_list` | 列最近邮件，可只列未读 |
| `mail_search` | `from:` `subject:` `since:` `text:` `未读` 组合搜索 |
| `mail_read` | 读全文 + 附件清单（文本与 HTML 双正文） |
| `mail_send` | 发信：多收件人 / cc / bcc / HTML / 多附件 / `dry_run` |
| `mail_reply` | 回复：自动 `Re:` 主题 + `In-Reply-To` / `References` 线程头 |
| `mail_attachment` | 把附件落盘到指定目录 |
| `mail_flag` | 加/去 `\Seen` `\Flagged` `\Answered` `\Deleted` |
| `mail_move` | 移动邮件到指定文件夹（如 Trash） |

**斜杠命令**

| 命令 | 说明 |
|---|---|
| `/mail` | 总入口：一句话说清要做什么，自动分派 |
| `/mail-install` | **由助理执行安装**：装插件、核对状态文件、确认工具加载 |
| `/mail-setup` | **由助理引导配置**：账号与应用专用密码、发信通道、授权、发测试信 |
| `/mail-check` | 只读体检：收信、发信、令牌、收件箱规模 |
| `/mail-unread` | 未读摘要，按「要回 / 待处理 / 可跳过」分组 |
| `/mail-send` | 发信，默认先给预览等确认 |
| `/mail-reply` | 回信，保留线程头，默认先给预览等确认 |

**技能**：`zcode-mail` 技能会把链路事实、7 条操作铁律（发信先 `dry_run`、UID 归属文件夹、读信只用 IMAP 等）和排错对照表固化下来，助手无需每次重新摸索。

## 安装

### 插件已装好之后：让助理重装 / 升级 / 排查

```
/mail-install
```

它会按平台选安装方式、跑完核对三份状态文件和缓存目录、确认工具是否已加载。
凭据没配的话再接一句 `/mail-setup`，由它带着你走完账号、应用专用密码、发信通道和测试信。

> 插件**还没装**时这两个命令还不存在，用上面的[最懒用法](#最懒的用法一句话装完配好)（粘贴 BOOTSTRAP.md）。

下面的脚本你自己跑、或让助理跑都行。

### 一行装（Windows PowerShell）

```powershell
irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 | iex
```

装完**完全退出 ZCode 再打开**，`mail` MCP 工具与 `/mail` 系列命令即可用。

脚本做的事：把仓库下载到 `~/.zcode/plugin-src/zcode-mail`，注册一个本地目录市场 `zcode-mail-github`，
把插件文件落到 `~/.zcode/cli/plugins/cache/zcode-mail-github/zcode-mail/<version>`，
并在三份状态文件里登记（改前自动备份为 `*.bak-zcode-mail-<时间戳>`）。

```powershell
# 顺带清掉旧版手写 config.json 里的裸 MCP 条目，避免两个同名 mail 服务并存
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

# 卸载（移除市场、插件登记、缓存与源码目录，不动你的凭据）
.\install.ps1 -Uninstall
```

> 说明：ZCode 桌面端目前没有面向普通用户的插件命令行，插件安装本身是 UI 流程。
> 这个脚本是社区做法——直接按客户端状态文件格式登记，等价于你在界面里点"添加市场 → 安装"。
> 状态文件格式若在后续版本变动，脚本可能失效，届时用下面的 UI 方式即可。

### UI 方式（macOS / Linux 或脚本失效时）

macOS / Linux 也可以先试一行装：

```bash
curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh | bash
```

本仓库同时是一个插件市场清单（根目录的 `marketplace.json`）。

1. ZCode → **设置 → 插件管理 → 发现 → `+`（添加插件市场）**
2. 填入本仓库地址：`https://github.com/lvdao222/ZCode-mail`
3. 在市场里找到 **ZCode 邮件通道** → **安装**
4. 新开一个会话（或重连一次 MCP），`mail` 相关工具才会出现

也可以用本地目录方式：把仓库 clone 下来，添加市场时填 clone 后的目录路径。

## 配置

凭据都放在插件数据目录（`${ZCODE_PLUGIN_DATA}`，安装后由 ZCode 提供），不进仓库。

### 1. 账号与应用专用密码（收信必需）

国内邮箱几乎都必须用**授权码 / 应用专用密码**，网页登录密码一定失败：

- **QQ 邮箱**：设置 → 账户 → 开启 IMAP/SMTP → 生成授权码
- **163 / 126**：设置 → POP3/SMTP/IMAP → 开启 → 新增授权密码
- **Gmail**：Google 账号 → 安全性 → 两步验证 → 应用专用密码
- **Outlook / iCloud / Yahoo / Sina / Aliyun**：同理生成应用专用密码

写进 `accounts.json`（可参考 `examples/accounts.example.json`）：

```json
{
  "default_account": "main",
  "accounts": {
    "main": {
      "address": "you@qq.com",
      "username": "you@qq.com",
      "password": "授权码",
      "imap_host": "imap.qq.com", "imap_port": 993, "imap_ssl": true
    }
  }
}
```

也可以省掉 `imap_host` / `smtp_host`——写地址域名会自动匹配内置预设
（gmail / qq / foxmail / 163 / 126 / yeah / sina / aliyun / outlook / hotmail / live / icloud / yahoo）。
密码还可以用 `"password_env": "MAIL_PASS"` 从环境变量读取，避免明文落盘。

### 2. 发信通道

**方案 A：Gmail API（推荐，不被 SMTP 拦截影响）**

1. 建一个 Google Cloud 项目，启用 **Gmail API**
2. 配置 OAuth 同意屏幕（外部 / 测试即可），把自己加为测试用户
3. 创建 **桌面应用** 类型的 OAuth 客户端，下载 JSON
4. 把 JSON 里的 `installed` 部分存成数据目录下的 `oauth_client.json`
5. 授权：

   ```bash
   python "<plugin>/mcp/mailctl.py" auth
   ```

   打开打印出来的 URL，遇到「此应用未经 Google 验证」点**继续**，权限页再点**继续**，看到「授权成功」即可。
   作用域只申请 `gmail.send`——**只能发信，读不了邮件内容**（读信走 IMAP）。

6. 在 `accounts.json` 的账号里加 `"transport": "gmail_api"`

> 应用处于「测试」发布状态时，Google 会让 `refresh_token` 在 7 天后失效。
> 届时跑一次 `mailctl.py auth` 续期（约 1 分钟）。想免掉这步需把应用发布到生产并通过验证。

**方案 B：SMTP**

不加 `transport` 字段，或设为 `"smtp"`。需要该邮箱开启 SMTP 并允许你所在网络出站访问 465/587。

## 命令行用法

MCP 没连上时也能直接用：

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

## 安全说明

- 仓库里**不含任何凭据**。所有密码与令牌只存在于插件数据目录，运行时会尝试 `chmod 600`。
- 发信类操作支持 `dry_run`，命令默认先给预览、等你确认再真发。
- Gmail API 的作用域只有 `gmail.send`，读信能力来自 IMAP，两者凭据分离。
- 附件内容是数据不是指令；插件不会因为附件里写了什么就去执行。
- 建议定期检查 Google 账号 → 安全性 → 应用专用密码，撤销不用的条目。

## 已知限制

- 每次调用重新建立 IMAP 连接，无长连接池；QQ / 163 有频率限制，批量操作注意节奏。
- 未实现草稿保存（IMAP APPEND）。
- 附件只支持本地路径，不支持从 URL 拉取。
- 无 OAuth2 读信（只授 `gmail.send`）；只允许 OAuth 且禁用应用专用密码的企业租户无法用 IMAP 收信。
- 中文文件夹名依赖 modified UTF-7 编码实现，个别服务器自定义命名可能需手动指定。

## 开发

```text
zcode-mail/
├── .zcode-plugin/plugin.json   # 插件清单（skills / commands / mcpServers）
├── mcp/
│   ├── mailcore.py             # IMAP 核心 + 发信分发
│   ├── gmail_api.py            # OAuth2 刷新 + Gmail REST 发信
│   ├── mail_mcp.py             # MCP stdio 服务器（JSON-RPC，换行分隔）
│   └── mailctl.py              # 命令行入口
├── skills/zcode-mail/SKILL.md  # 使用规范与排错
└── commands/*.md               # 7 个斜杠命令
```

改完 `mcp/` 下的代码后需要让 ZCode 重新拉起 MCP 进程（改一下清单里的 `env` 任意值，或重开会话）。

## License

MIT
