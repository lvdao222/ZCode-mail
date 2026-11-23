---
description: 只读体检邮件通道：IMAP 收信、Gmail API 发信、OAuth 令牌状态、收件箱规模（不发信不改状态）
allowed-tools: mcp__mail__mail_accounts, mcp__mail__mail_check, Bash
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`），做**纯只读**体检。

1. `mail_accounts` 拿账号与配置文件路径。
2. `mail_check`（**不要**传 `test_send_to`，这个命令不发信）。
3. 如果 `mail_check` 超时或 `transport` 缺失，说明进程退回 SMTP 了：
   用 Bash 跑 `python "${CLAUDE_PLUGIN_ROOT}/mcp/mailctl.py" check` 复核，
   并检查数据目录里 `accounts.json` 是否还有 `"transport": "gmail_api"`。
4. 中文汇总成一张表：账号 / IMAP 端点与是否通 / 发信通道 / 令牌是否有效 / 令牌剩余天数 / 收件箱总数与未读数。
5. 结论只给三种之一：「收发都可用」「只能收不能发（原因）」「不可用（原因）」。

要求：

- 不修改任何邮件状态（不 `\Seen`、不移动、不删除）。
- 不打印 `accounts.json` / `token.json` 里的密码或令牌明文，只给掩码或布尔值。
- 令牌不足 2 天时提醒用户跑 `python "${CLAUDE_PLUGIN_ROOT}/mcp/mailctl.py" auth`。

用户附加要求：$ARGUMENTS
