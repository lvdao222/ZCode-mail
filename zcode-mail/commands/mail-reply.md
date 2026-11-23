---
description: 回复邮件：定位原邮件、保留线程头，默认先给预览等确认
argument-hint: 例如「回 uid 1543，说明天处理」或「回刚才那封，附上报价单.pdf」
allowed-tools: mcp__mail__mail_search, mcp__mail__mail_read, mcp__mail__mail_reply, Bash
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`）。

用户的需求：$ARGUMENTS

流程：

1. **定位原邮件**，按优先级：
   - 用户给了 uid → 直接用（注意 uid 属于某个文件夹，默认 `INBOX`）
   - 用户说「刚才那封 / 上一封 / 他发的那封」→ 用 `mail_search`（`from:` / `subject:` / `since:`）或 `mail_list` 定位
   - 定位到多封候选 → 列表给用户选，**不要自己挑一封就回**
2. **先读原文**：`mail_read` 拿主题、发件人、正文，确认回对人、回对事。
3. **组装回复**：`body` 写用户要表达的内容；`reply_all` 仅在用户要求或原邮件有多人收件且明显需要群答时使用；
   `quote` 默认保留引用，用户嫌长再关。
4. **先发预览**：`mail_reply` 带 `dry_run: true`，展示：回复给谁（含抄送）、主题（自动 `Re:`）、正文全文、附件、线程头是否带上。
5. **等确认**后 `dry_run: false` 真发，回报 `gmail_id` 与 labels。

硬性要求：

- 回复是外发动作：**没有明确确认不许真发**。
- 不要改原邮件主题（除自动补 `Re:`）；不要把私聊内容扩展到未出现的收件人。
- 引用原文保留即可，不要删改对方说过的话。
- 找不到原邮件就直说找不到并给出已搜过的条件，不要编造 uid。
