---
description: 由助理执行安装：装好 ZCode Mail 插件并确认工具可用（Windows 走 install.ps1，macOS/Linux 走 install.sh）
argument-hint: 例如「装到默认位置」「顺便清掉旧的裸 MCP 条目」
allowed-tools: Bash, Read, Write, Edit
---
加载 `zcode-mail` 技能（`${CLAUDE_PLUGIN_ROOT}/skills/zcode-mail/SKILL.md`），由你（助理）替用户完成安装，不要让他自己去敲命令。

用户这次的附加要求：$ARGUMENTS

## 步骤

1. **判定平台**。Windows → `install.ps1`；macOS / Linux → `install.sh`。
   用 Bash 跑 `uname -s`（Git Bash 下也适用）确认，别猜。

2. **确认前置条件**：
   - `~/.zcode/cli` 存在（ZCode 桌面端至少启动过一次），不存在就停下并说明。
   - `python` 或 `python3` 可执行（插件的 MCP 服务需要它）。

3. **执行安装**：

   Windows（PowerShell）：
   ```powershell
   irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 | iex
   ```
   若用户机器上已有手写的 `mcp.servers.mail` 条目，加 `-RemoveLegacyMcp`：
   ```powershell
   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp
   ```

   macOS / Linux：
   ```bash
   curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh | bash
   ```

4. **核对落盘结果**（必须实际读文件，不要凭"应该成功了"下结论）：
   - `~/.zcode/cli/plugins/installed_plugins.json` 里有 `zcode-mail@zcode-mail-github`
   - `~/.zcode/cli/plugins/known_marketplaces.json` 里有 `zcode-mail-github`
   - `~/.zcode/cli/config.json` 的 `plugins.enabledPlugins` 里该键为 `true`
   - `~/.zcode/cli/plugins/cache/zcode-mail-github/zcode-mail/<version>/` 下 `.zcode-plugin/plugin.json` 存在

5. **确认工具是否已加载**：如果当前会话能看到 `mcp__plugin_zcode-mail_mail__*` 工具，直接跑一次 `mail_check` 验证；
   看不到就明确告诉用户「需要完全退出 ZCode 再打开」，这一步不要含糊过去。

6. **报告**：插件版本、安装路径、数据目录、工具是否就绪。
   若凭据还没配（`mail_check` 报缺少账号或未授权），紧接着引导用户走 `/mail-setup`，不要就此结束。

## 硬性要求

- **不打印任何凭据明文**；不把用户的应用专用密码、OAuth 令牌写进聊天或命令历史。
- 不擅自修改用户其它插件或无关配置；`config.json` 只动 `plugins.enabledPlugins` 与（用户同意时的）`mcp.servers.mail`。
- 安装失败就贴出原始报错并给出下一步，不要重试风暴，也不要谎报成功。
