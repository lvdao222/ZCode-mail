---
description: 邮件通道总入口：一句话说清要做什么（看未读 / 搜信 / 读信 / 发信 / 回信 / 下附件），我按规矩执行
argument-hint: 例如「看看今天的未读」「搜上周的发票」「回这封说明天处理」
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`），按里面的链路和铁律办事。

用户这次的诉求：$ARGUMENTS

如果上面是空的，就只做体检并给用法，不要擅自发信：

1. MCP 工具 `mail_accounts` 确认默认账号与配置文件路径。
2. MCP 工具 `mail_check` 报告 IMAP 是否通、发信通道是 `gmail_api` 还是 SMTP、OAuth 令牌是否有效、收件箱总数/未读数。
3. 输出一份中文速览：账号 · 收信通道 · 发信通道 · 未读数 · 令牌剩余时间 · 可用能力（`mail_list` `mail_search` `mail_read` `mail_send` `mail_reply` `mail_attachment` `mail_flag` `mail_move`）。
4. 末尾给三条可直接照抄的示例，比如「搜上周的发票」「把 uid 1543 的附件下到 .\downloads」「回 uid 1543 说明天处理」。

如果诉求非空，就解析成具体操作再执行：

- 「未读」→ `mail_list` 带 `unread_only: true`
- 「搜…」→ `mail_search`，把中文条件翻成 `from:` / `subject:` / `since:` / `text:` 组合
- 「读…」/「这封」→ 先 `mail_search` 或 `mail_list` 拿 uid，再 `mail_read`
- 「发…」→ 组装 `mail_send`，**先 `dry_run: true` 给用户过目**，确认后再真发
- 「回…」→ 先定位 uid，再用 `mail_reply`，同样先 `dry_run`
- 「附件」→ `mail_attachment` 落盘，报告保存路径与大小

硬性要求：不要凭空编造 uid、收件人或邮件内容；把关键字段（发件人、主题、时间）如实回显给用户。
