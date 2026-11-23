# BOOTSTRAP — 让助理一路装到「能发信」为止

> **给用户看的**：把下面这句话整段复制进 ZCode 对话框发送即可，其余交给助理。
>
> ```
> 读一下 https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
> 然后照着帮我把邮件插件装好、邮箱配好，最后发一封测试信给我确认收到。
> ```

---

> **给助理看的**：你正在执行 ZCode Mail 的无人值守安装。用户只说了「装好配好」，没有给你平台、邮箱、密码。
> 按下面的阶段推进，**每阶段结束都要用命令核对事实，不许凭"应该成功了"往下走**。
> 全程遵守文末的硬性约束。

## 阶段 0：探明环境（30 秒）

```bash
uname -s                      # Darwin / Linux / MINGW64_NT-*（Git Bash 视为 Windows）
python -V 2>/dev/null || python3 -V 2>/dev/null
ls ~/.zcode/cli               # 必须存在，否则 ZCode 从没启动过 -> 停止并说明
```

判定：

| 结果 | 走哪条路 |
|---|---|
| `MINGW*` / PowerShell 可用 | Windows → 用 `install.ps1` |
| `Darwin` / `Linux` | → 用 `install.sh` |
| `~/.zcode/cli` 不存在 | **停止**：让用户先装 ZCode 桌面端并启动一次 |
| 找不到可用的 `python`/`python3` | **停止**：插件运行时需要 Python，先装 |

## 阶段 1：装插件

Windows（PowerShell）：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp
```

macOS / Linux：

```bash
curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh | bash -s -- --remove-legacy-mcp
```

`--remove-legacy-mcp` / `-RemoveLegacyMcp` 的作用：清掉 `config.json` 里手写的 `mcp.servers.mail`，
避免两个同名 `mail` 服务互相遮蔽。用户之前没手工配过就无所谓，加上更安全。

安装脚本失败时：读它的报错，**按报错修**（常见：`~/.zcode/cli` 不存在、Python 缺失、网络打不开 codeload），
不要改去手写状态文件硬凑。

## 阶段 2：核对安装真的落地

逐条查，全部满足才算装好：

```bash
# 1. 插件登记
grep -q 'zcode-mail@zcode-mail-github' ~/.zcode/cli/plugins/installed_plugins.json && echo OK1

# 2. 市场登记
grep -q 'zcode-mail-github' ~/.zcode/cli/plugins/known_marketplaces.json && echo OK2

# 3. 启用状态（值必须是 true）
grep -A2 'zcode-mail@zcode-mail-github' ~/.zcode/cli/config.json | head -3

# 4. 缓存目录里的清单存在
ls ~/.zcode/cli/plugins/cache/zcode-mail-github/zcode-mail/*/.zcode-plugin/plugin.json
```

然后判断工具是否已加载：

- 若当前会话已有 `mcp__plugin_zcode-mail_mail__*` 工具 → 直接跑一次 `mail_check`，进阶段 3。
- 若没有 → 明确告诉用户「**请完全退出 ZCode 再打开**」，等其重启。别谎称已就绪。

## 阶段 3：配账号（收信）

数据目录一般是 `~/.zcode/cli/plugins/data/zcode-mail@zcode-mail-github/`，
里面应有 `accounts.json`（没有就从空模板建）。**先 `ls` 确认实际路径，别照抄**。

问用户三件事，一次问清：

1. 邮箱地址
2. 服务商（Gmail / QQ / 163 / 126 / Outlook / iCloud / 自建域名…）
3. 这个邮箱能否开启 IMAP

然后引导取**应用专用密码**（网页登录密码 100% 失败）：

| 服务商 | 位置 |
|---|---|
| QQ 邮箱 | 设置 → 账户 → 开启 IMAP/SMTP → 生成授权码 |
| 163 / 126 / yeah | 设置 → POP3/SMTP/IMAP → 开启 → 新增授权密码 |
| Gmail | Google 账号 → 安全性 → 两步验证 → 应用专用密码 |
| Outlook / iCloud / Yahoo | 账号安全设置里生成应用密码 |

**密码不要粘进聊天。** 二选一，由用户自己完成最后一米：

- 让用户自己编辑 `accounts.json`（把路径、字段、示例发给他），或
- 让用户设环境变量，你在配置里写 `"password_env": "MAIL_PASS"`

最小配置（域名可自动匹配内置预设，不必写 host）：

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

写完跑 `mail_check`，`imap_ok` 必须为 `true`。为 `false` 就把原始报错贴给用户并给出下一步
（最常见：用了网页密码、IMAP 没开、或需要授权码）。

## 阶段 4：配发信通道

先看 `mail_check` 里的 `transport` 与 `smtp_ok`：

**默认先试 SMTP**（配置最省事）：账号里不加 `transport` 或写 `"smtp"`，再跑 `mail_check`。
`smtp_ok: true` 就到此为止。

**SMTP 不通时**（465 握手超时、587/25 被直接关闭，而 IMAP 正常）改走 Gmail API：

1. 带用户在 Google Cloud 建项目、启用 Gmail API
2. OAuth 同意屏幕：外部 + 测试，把自己加为测试用户
3. 建**桌面应用**类型客户端，把 `installed` 部分存成数据目录下的 `oauth_client.json`
4. 跑授权：

   ```bash
   python "<插件路径>/mcp/mailctl.py" auth
   ```

   它会打印 URL 并起 `127.0.0.1:8765` 本地回调。让用户在浏览器打开：遇到
   「此应用未经 Google 验证」点**继续**，权限页再点**继续**，看到「授权成功」即可。
5. 账号里加 `"transport": "gmail_api"`

作用域只申请 `gmail.send`：**只能发信，读不了邮件**，读信走 IMAP。这点必须跟用户讲明。

## 阶段 5：端到端验证（不许跳过）

1. `mail_check`：`imap_ok` 与 `smtp_ok` 都应为 `true`。
2. 先 `dry_run` 给用户过目：
   `mail_send(to=<用户邮箱>, subject="ZCode 邮件通道自检", body="...", dry_run=true)`
3. 用户确认后真发。
4. **回查收件箱**确认真的收到了：`mail_search(query="subject:ZCode")` 或 `mail_list(limit=3)`。
5. 把最终状态讲清楚：账号、收信端点、发信通道、令牌剩余天数。

## 阶段 6：交付说明

一段话收尾，包含：

- 已装版本与安装路径
- 数据目录路径（凭据放这里）
- 现在能用什么：`/mail` `/mail-check` `/mail-unread` `/mail-send` `/mail-reply`
- Gmail API 令牌 7 天过期的提醒，以及续期只需一条：`python "<插件路径>/mcp/mailctl.py" auth`
- 卸载方式：`.\install.ps1 -Uninstall`（Windows）或 `./install.sh --uninstall`（macOS/Linux）

## 硬性约束

1. **凭据永不进聊天、不进命令历史、不进任何提交**。回显只给掩码或布尔值。
2. **不伪造端点**。不确定某域名是否支持 IMAP，就说清不确定并给验证方法。
3. **改任何状态文件前先备份**；`config.json` 只动 `plugins.enabledPlugins` 与 `mcp.servers.mail`，
   不碰用户其它插件与无关配置。
4. **不谎报成功**。失败就贴原始报错 + 下一步动作；不重试风暴，不静默换方案。
5. **该停就停**：缺 ZCode、缺 Python、缺密码时停下来问，不要自己编一个。

---

## For English-speaking users

Paste this into the ZCode chat:

```
Read https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
and follow it to install the mail plugin, configure my mailbox, then send me a
test email and confirm it actually arrived.
```

The assistant will detect your platform, run `install.ps1` (Windows) or `install.sh` (macOS / Linux),
verify the plugin state files, walk you through an app password, pick the sending channel
(SMTP first, Gmail API over HTTPS 443 when SMTP ports are filtered), and verify end to end.

Two rules you should expect it to follow: it never asks you to paste a password into the chat,
and it never claims success without reading the state files and round-tripping a real message.
