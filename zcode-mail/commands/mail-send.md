---
description: 发邮件：按一句话需求起草并发送，默认先给预览等确认，不确认不真发
argument-hint: 例如「发给 a@b.com，主题：周报，正文：本周完成 X，附件 ./r.pdf」
allowed-tools: mcp__mail__mail_send, mcp__mail__mail_check, Bash
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`）。

用户的需求：$ARGUMENTS

流程（顺序不能跳）：

1. **抽取字段**：`to`（必填，多个用逗号）、`cc`、`bcc`、`subject`、`body`、`html_body`、`attachments`（本地路径）。
   缺 `subject` 就根据正文拟一个，别留空；缺 `to` 就**停下问用户**，不要猜邮箱。
2. **附件先验证存在**：用 Bash `ls` 确认每个附件路径真实存在、大小合理；不存在就报路径错，不要静默丢掉附件。
3. **先发预览**：调用 `mail_send` 带 `dry_run: true`，把结果整理成确认单给用户看——
   发件账号 · 收件人 · 抄送/密送 · 主题 · 正文全文 · 附件名与大小 · 预计大小。
   结尾一句：「确认发送就回我一句『发』」。
4. **等确认**。用户明确说发/确认/OK 之后，才用 `dry_run: false` 真发。
5. **回报结果**：`gmail_id`、`message_id`、Gmail 给出的 labels（应含 `SENT`）。失败就把 API 原始错误贴出来，不要粉饰。

硬性要求：

- 「发邮件」属于不可撤销的外发动作：**没拿到明确确认，不许真发**。用户在这条命令里预先写了「直接发」才可跳过预览。
- 收件人必须来自用户原话或上下文；不要依据历史邮件推测收件人。
- 正文用用户给的内容，可润色措辞但不得改变事实、金额、日期、承诺。
- 中文正文默认纯文本（`body`）；用户要求排版才用 `html_body`。
