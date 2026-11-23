---
description: 由助理引导配置邮箱：账号与应用专用密码、Gmail API 授权、发测试信验证
argument-hint: 例如「配 Gmail」「配 QQ 邮箱 you@qq.com」「我要走 SMTP 不用 API」
allowed-tools: Bash, Read, Write, Edit, mcp__plugin_zcode-mail_mail__mail_check, mcp__plugin_zcode-mail_mail__mail_accounts, mcp__plugin_zcode-mail_mail__mail_send
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`），把配置这件事**带着用户走完**，不要丢一份文档让他自己啃。

用户这次的附加要求：$ARGUMENTS

## 第 0 步：定位数据目录

插件数据目录由 ZCode 提供（清单里的 `${ZCODE_PLUGIN_DATA}`）。用 Bash 确认实际路径，例如：

```bash
ls ~/.zcode/cli/plugins/data/
```

目录名形如 `zcode-mail@zcode-mail-github`；里面应有 `accounts.json`、`oauth_client.json`、`token.json`
（首次运行时这些由旧目录自动迁移，可能还不存在）。**不要凭猜**，以实际存在为准，并在回复里报出该路径。

## 第 1 步：账号与应用专用密码（收信必需）

1. 问清用户的邮箱地址与所属服务商（Gmail / QQ / 163 / Outlook / iCloud / 自建域名…）。
2. 告诉他去哪里生成**应用专用密码 / 授权码**，并强调**网页登录密码一定失败**：
   - QQ 邮箱：设置 → 账户 → 开启 IMAP/SMTP → 生成授权码
   - 163 / 126：设置 → POP3/SMTP/IMAP → 开启 → 新增授权密码
   - Gmail：Google 账号 → 安全性 → 两步验证 → 应用专用密码
   - Outlook / iCloud / Yahoo：同理由账号安全设置生成
3. **不要让用户把密码贴进聊天。** 二选一：
   - 推荐：让他自己编辑 `accounts.json`（把模板路径给他，字段说清），或
   - 让他设置环境变量（`MAIL_PASS`），配置里写 `"password_env": "MAIL_PASS"`。
4. 域名能自动匹配预设（gmail / qq / foxmail / 163 / 126 / yeah / sina / aliyun / outlook / hotmail /
   live / icloud / yahoo），所以通常只填 `address` + `username` + `password(_env)` 就够。

## 第 2 步：发信通道

先跑 `mail_check`，看 `transport` 与 `smtp_ok`：

- **能走 SMTP 就走 SMTP**（配置最省心）：账号里不加 `transport` 或写 `"smtp"`。
- **SMTP 被网络拦截时**（465 握手超时、587/25 被关）改走 **Gmail API**：
  1. 引导用户在 Google Cloud 建项目、启用 Gmail API
  2. 配置 OAuth 同意屏幕（外部 / 测试），把自己加为测试用户
  3. 创建**桌面应用**类型客户端，把 `installed` 部分存成数据目录下的 `oauth_client.json`
  4. 跑授权（会打印 URL 并起 `127.0.0.1:8765` 本地回调）：

     ```bash
     python "<插件路径>/mcp/mailctl.py" auth
     ```

     让用户在浏览器打开该 URL：遇到「此应用未经 Google 验证」点**继续**，权限页再点**继续**。
  5. 账号里加 `"transport": "gmail_api"`

作用域只申请 `gmail.send`：**只能发信，读不了邮件内容**，读信仍走 IMAP。这点要跟用户说明白。

## 第 3 步：验证

1. `mail_check`：`imap_ok` 与 `smtp_ok` 都应为 true。
2. 发测试信 **先 `dry_run`** 给用户过目，确认后再真发：

   ```
   mail_send(to=<用户邮箱>, subject="ZCode 邮件通道自检", body="...", dry_run=true)
   ```

   真发之后用 `mail_list` / `mail_search` 确认真的收到了。

3. 把最终状态讲清楚：账号、收信端点、发信通道、令牌剩余天数（Gmail API 测试态 7 天会过期）。

## 硬性要求

- 全程**不打印凭据**；回显只给掩码或布尔值。
- 不确定用户邮箱域是否支持 IMAP 时，直接说清不确定并给验证方式，不要编造端点。
- 任何一步失败，贴原始报错 + 下一步动作，不要静默换方案。
- 配完提醒：`refresh_token` 若 7 天后过期，重新跑一次 `mailctl.py auth` 即可。
