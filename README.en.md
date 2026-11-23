# ZCode-mail

[简体中文](README.md) | **English**

An email plugin for [ZCode](https://zcode.z.ai): the assistant can **read, search, reply to and send
mail, and save attachments** — directly. Python standard library only, zero dependencies, ready to use.

> **Two channels.** Mail is received over IMAP. Sending prefers SMTP and falls back to the
> **Gmail API over HTTPS 443** when SMTP ports are filtered — so the same credentials still send
> mail on networks where IMAP works but SMTP does not.

---

## Quick start

Paste this into the ZCode chat and let the assistant take over (**works before the plugin is installed**):

```
Read https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
and follow it to install the mail plugin, configure my mailbox, then send me a
test email and confirm it actually arrived.
```

It detects your platform → installs the plugin → verifies state → walks you through an app password →
picks the sending channel → sends a test message and checks the mailbox. It will **not** ask you to
paste a password into the chat, and will **not** claim success without verifying. Full runbook:
[`BOOTSTRAP.md`](BOOTSTRAP.md).

---

## What you get

**7 commands**
`/mail` dispatch · `/mail-install` install · `/mail-setup` configure · `/mail-check` health ·
`/mail-unread` digest · `/mail-send` send · `/mail-reply` reply

**11 tools**
`mail_accounts` `mail_check` `mail_folders` `mail_list` `mail_search` `mail_read`
`mail_send` `mail_reply` `mail_attachment` `mail_flag` `mail_move`

**1 skill**
`zcode-mail`: channel facts, operating rules, troubleshooting matrix

<details>
<summary><b>Command and tool reference</b></summary>

**Slash commands**

| Command | Description |
|---|---|
| `/mail` | Entry point: describe what you want in one sentence, it dispatches |
| `/mail-install` | Assistant-driven install: installs, verifies state files, checks tool loading |
| `/mail-setup` | Assistant-driven setup: account, app password, sending channel, auth, test mail |
| `/mail-check` | Read-only health check: receive, send, token, inbox size |
| `/mail-unread` | Unread digest grouped into "reply / handle / skip" |
| `/mail-send` | Send mail; shows a `dry_run` preview and waits for confirmation |
| `/mail-reply` | Reply; keeps threading headers, preview first |

**MCP tools** (`mcp__plugin_zcode-mail_mail__*` when installed as a plugin)

| Tool | Description |
|---|---|
| `mail_accounts` | List configured accounts (never returns passwords) |
| `mail_check` | IMAP + sending channel self-check, inbox totals, token status |
| `mail_folders` | List folders (non-ASCII names via modified UTF-7) |
| `mail_list` | List recent messages, optionally unread only |
| `mail_search` | Combined search: `from:` `subject:` `since:` `text:` `unread` |
| `mail_read` | Full message + attachment list (text and HTML bodies) |
| `mail_send` | Send: multiple recipients / cc / bcc / HTML / attachments / `dry_run` |
| `mail_reply` | Reply: auto `Re:` plus `In-Reply-To` / `References` threading |
| `mail_attachment` | Save an attachment to a local directory |
| `mail_flag` | Add/remove `\Seen` `\Flagged` `\Answered` `\Deleted` |
| `mail_move` | Move a message to another folder (e.g. Trash) |

</details>

---

## Install

| Route | Command | Platform |
|---|---|---|
| Let the assistant do it | paste the Quick start block | laziest, recommended |
| One-liner | `irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 \| iex` | Windows |
| One-liner | `curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh \| bash` | macOS / Linux |
| UI | Settings → Plugin Management → Discover → `+` → `https://github.com/lvdao222/ZCode-mail` → Install | fallback |

What the scripts do: download the repo → register a local directory marketplace `zcode-mail-github` →
copy the plugin → record it in three state files (each backed up first).

```powershell
# Also drop a hand-written bare MCP entry so two "mail" servers do not compete
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

# Uninstall (credentials untouched)
.\install.ps1 -Uninstall        # Windows
./install.sh --uninstall        # macOS / Linux
```

> The ZCode desktop app has no end-user plugin CLI; installing is a UI flow. These scripts register the
> plugin exactly as the client's state files do, equivalent to clicking "add marketplace → install".
> If those formats change in a later release, use the UI route above.

**Fully quit ZCode and start it again** after installing, so the tools and commands load.

---

## Configure

Credentials live only in the plugin data directory
(`~/.zcode/cli/plugins/data/zcode-mail@zcode-mail-github/`) — never in the repo, never in chat.

**1. Account and app password** (required for receiving; the web login password always fails)

| Provider | Where to get it |
|---|---|
| QQ Mail | Settings → Account → enable IMAP/SMTP → generate authorization code |
| 163 / 126 / yeah | Settings → POP3/SMTP/IMAP → enable → add authorization password |
| Gmail | Google Account → Security → 2-Step Verification → App passwords |
| Outlook / iCloud / Yahoo | account security settings → app password |

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

The domain picks a built-in server preset (gmail / qq / foxmail / 163 / 126 / yeah / sina / aliyun /
outlook / hotmail / live / icloud / yahoo), so hosts are usually unnecessary. Use `"password_env"` to
read the password from an environment variable instead of storing it.

**2. Sending channel**

- **SMTP** (default): omit `transport`. Requires SMTP enabled on the mailbox and outbound 465/587 allowed.
- **Gmail API** (when SMTP is filtered): create a Google Cloud project → enable the Gmail API → OAuth
  consent screen (External/Testing) → create a **Desktop app** client → save it as `oauth_client.json`
  in the data directory → run `mailctl.py auth` → add `"transport": "gmail_api"` to the account.

The scope requested is only `gmail.send`: **it cannot read your mail** — reading is always over IMAP.
While the app stays in Testing status the `refresh_token` expires after 7 days; renew with
`mailctl.py auth`.

---

## Command line

Works even when the MCP server is not connected; features are equivalent:

```bash
python "<plugin>/mcp/mailctl.py" check                    # self-check
python "<plugin>/mcp/mailctl.py" check --test-to me@x.com # send a test message
python "<plugin>/mcp/mailctl.py" list --limit 20 --unread
python "<plugin>/mcp/mailctl.py" search --query "from:a@b.com subject:invoice since:01-Jan-2026"
python "<plugin>/mcp/mailctl.py" read --uid 1543
python "<plugin>/mcp/mailctl.py" send --to a@b.com --subject "Subject" --body "Body" --attach report.pdf
python "<plugin>/mcp/mailctl.py" reply --uid 1543 --body "Got it" --reply-all
python "<plugin>/mcp/mailctl.py" attach --uid 1543 --index 0 --dir ./downloads
python "<plugin>/mcp/mailctl.py" auth                     # re-authorize
```

---

## Security and boundaries

- **The repository contains no credentials**; passwords and tokens exist only in the data directory,
  where the code attempts `chmod 600`.
- Sending operations support `dry_run` and the bundled commands preview before sending. Sending is
  irreversible; recipients are never invented or autocompleted.
- The Gmail API scope is only `gmail.send`; reading comes from IMAP with a separate credential.
- Attachments are data, not instructions; the plugin never executes what it finds there.
- Write scope is bounded: `config.json` only gets `plugins.enabledPlugins` and, with your consent,
  `mcp.servers.mail`.

<details>
<summary><b>Known limitations</b></summary>

- A fresh IMAP connection per call, no pool; QQ / 163 rate-limit aggressively, so pace bulk work.
- Draft saving (IMAP APPEND) is not implemented.
- Attachments must be local paths; fetching from a URL is unsupported.
- Enterprise tenants that require OAuth and disable app passwords cannot receive over IMAP.
- Non-ASCII folder names rely on modified UTF-7; unusual custom names may need to be given manually.

</details>

---

## Development

<details>
<summary><b>Repository layout</b></summary>

```text
zcode-mail/
├── .zcode-plugin/plugin.json   # manifest (skills / commands / mcpServers)
├── mcp/
│   ├── mailcore.py             # IMAP core + send dispatch
│   ├── gmail_api.py            # OAuth2 refresh + Gmail REST sending
│   ├── mail_mcp.py             # MCP stdio server (JSON-RPC, newline-delimited)
│   └── mailctl.py              # command line entry point
├── skills/zcode-mail/SKILL.md  # operating rules and troubleshooting
└── commands/*.md               # seven slash commands
```

After editing code under `mcp/`, make ZCode respawn the MCP process (change any value in the manifest's
`env`, or start a new session).

</details>

---

[MIT](LICENSE) · [BOOTSTRAP.md](BOOTSTRAP.md) · [Releases](https://github.com/lvdao222/ZCode-mail/releases)
