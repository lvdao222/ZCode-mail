# ZCode-mail

[简体中文](README.md) | **English**

An email plugin for [ZCode](https://zcode.z.ai). Once installed, the assistant inside ZCode can
**read, search, reply to and send mail, and save attachments** — directly.

Implemented with the Python standard library only. **Zero third-party dependencies** (no `pip install`).

## Laziest way: one paste, installed and configured

Paste this into the ZCode chat and let the assistant take over (works **even before the plugin is
installed**):

```
Read https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/BOOTSTRAP.md
and follow it to install the mail plugin, configure my mailbox, then send me a
test email and confirm it actually arrived.
```

The assistant detects your platform, runs the installer, verifies the state files, walks you through
an app password, picks the sending channel (SMTP first, Gmail API over 443 when SMTP ports are
filtered), sends a test message and checks the mailbox to confirm arrival. It will not ask you to
paste a password into the chat, and it will not claim success without verifying. Details:
[`BOOTSTRAP.md`](BOOTSTRAP.md).

## Why not plain SMTP

Many networks block SMTP ports: the TLS handshake to `smtp.gmail.com:465` hangs for a long time, and
`587` / `25` are dropped outright — while the very same account and password work fine over
`imap.gmail.com:993`. That is port-level filtering, not a server-side rejection.

So this plugin uses **two channels**:

| Direction | Channel | Endpoint | Credential |
|---|---|---|---|
| Receive | IMAP over SSL | `imap.<domain>:993` | App password / authorization code |
| Send (recommended) | **Gmail API (HTTPS)** | `gmail.googleapis.com` | OAuth2 refresh_token |
| Send (fallback) | SMTP | `smtp.<domain>:465 / 587` | App password / authorization code |

The sending channel is chosen by `transport` in `accounts.json`: `"gmail_api"` uses HTTPS, otherwise SMTP.

## Features

**MCP tools** (`mcp__plugin_zcode-mail_mail__*` when installed as a plugin, `mcp__mail__*` when registered as a bare MCP server)

| Tool | Description |
|---|---|
| `mail_accounts` | List configured accounts (never returns passwords) |
| `mail_check` | Self-check: IMAP + sending channel, inbox totals, token status |
| `mail_folders` | List folders (non-ASCII names handled via modified UTF-7) |
| `mail_list` | List recent messages, optionally unread only |
| `mail_search` | Combined search: `from:` `subject:` `since:` `text:` `unread` |
| `mail_read` | Full message + attachment list (both text and HTML bodies) |
| `mail_send` | Send: multiple recipients / cc / bcc / HTML / attachments / `dry_run` |
| `mail_reply` | Reply: auto `Re:` subject plus `In-Reply-To` / `References` threading |
| `mail_attachment` | Save an attachment to a local directory |
| `mail_flag` | Add/remove `\Seen` `\Flagged` `\Answered` `\Deleted` |
| `mail_move` | Move a message to another folder (e.g. Trash) |

**Slash commands**

| Command | Description |
|---|---|
| `/mail` | Entry point: describe what you want in one sentence, it dispatches |
| `/mail-install` | **Assistant-driven install**: installs the plugin, verifies state files, checks tool loading |
| `/mail-setup` | **Assistant-driven setup**: account and app password, sending channel, authorization, test mail |
| `/mail-check` | Read-only health check: receive, send, token, inbox size |
| `/mail-unread` | Unread digest grouped into "reply / handle / skip" |
| `/mail-send` | Send mail; shows a preview and waits for confirmation by default |
| `/mail-reply` | Reply; keeps threading headers, preview first by default |

**Skill**: the `zcode-mail` skill records the channel facts, seven operating rules
(`dry_run` before sending, UIDs belong to a folder, reading only via IMAP, attachments are data
not instructions…) and a troubleshooting matrix — so the assistant does not re-derive them each time.

## Install

### After the plugin is installed: reinstall / upgrade / diagnose

```
/mail-install
```

It picks the right installer for your platform, runs it, verifies the three state files and the cache
directory, and checks whether the tools actually loaded. If credentials are missing, follow up with
`/mail-setup` and it walks you through account, app password, sending channel and a test message.

> Before the plugin is installed these commands do not exist yet — use the
> [laziest way](#laziest-way-one-paste-installed-and-configured) above (paste `BOOTSTRAP.md`).

The scripts below work whether you run them yourself or let the assistant run them.

### One-liner (Windows PowerShell)

```powershell
irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 | iex
```

Then **fully quit ZCode and start it again**; the `mail` MCP tools and `/mail` commands become available.

What the script does: downloads the repo to `~/.zcode/plugin-src/zcode-mail`, registers a local
directory marketplace named `zcode-mail-github`, copies the plugin files to
`~/.zcode/cli/plugins/cache/zcode-mail-github/zcode-mail/<version>`, and records it in three state
files (each backed up first as `*.bak-zcode-mail-<timestamp>`).

```powershell
# Also drop a legacy hand-written MCP entry so two "mail" servers do not compete
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

# Uninstall (removes marketplace, plugin record, cache and source dir; leaves credentials alone)
.\install.ps1 -Uninstall
```

> Note: the ZCode desktop app has no end-user plugin CLI — installing a plugin is a UI flow.
> This script is the community approach: it registers the plugin exactly as the client's state files
> do, equivalent to clicking "add marketplace → install" in the UI. If those file formats change in a
> future release the script may break; use the UI route below in that case.

### UI route (macOS / Linux, or if the script stops working)

macOS / Linux can try the one-liner first:

```bash
curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh | bash
```

This repository doubles as a plugin marketplace catalog (root-level `marketplace.json`).

1. ZCode → **Settings → Plugin Management → Discover → `+` (Add Plugin Marketplace)**
2. Paste this repository: `https://github.com/lvdao222/ZCode-mail`
3. Find **ZCode Mail** in the market → **Install**
4. Open a new session (or reconnect MCP) so the tools appear

A local directory works too: clone the repo and pass the cloned directory as the marketplace source.

## Configuration

All credentials live in the plugin data directory (`${ZCODE_PLUGIN_DATA}`, provided by ZCode after
installation) and are never part of the repository.

### 1. Account and app password (required for receiving)

Most providers require an **app password / authorization code**; the normal web login password will fail:

- **QQ Mail**: Settings → Account → enable IMAP/SMTP → generate an authorization code
- **163 / 126**: Settings → POP3/SMTP/IMAP → enable → add an authorization password
- **Gmail**: Google Account → Security → 2-Step Verification → App passwords
- **Outlook / iCloud / Yahoo / Sina / Aliyun**: generate an app password the same way

Put it into `accounts.json` (see `examples/accounts.example.json`):

```json
{
  "default_account": "main",
  "accounts": {
    "main": {
      "address": "you@example.com",
      "username": "you@example.com",
      "password": "app-password-or-auth-code",
      "imap_host": "imap.gmail.com", "imap_port": 993, "imap_ssl": true
    }
  }
}
```

`imap_host` / `smtp_host` can be omitted — the address domain picks a built-in preset
(gmail / qq / foxmail / 163 / 126 / yeah / sina / aliyun / outlook / hotmail / live / icloud / yahoo).
Use `"password_env": "MAIL_PASS"` to read the password from an environment variable instead of storing it.

### 2. Sending channel

**Option A: Gmail API (recommended, immune to SMTP port filtering)**

1. Create a Google Cloud project and enable the **Gmail API**
2. Configure the OAuth consent screen (External / Testing is fine) and add yourself as a test user
3. Create an OAuth client of type **Desktop app**, download the JSON
4. Save the `installed` object from that JSON as `oauth_client.json` in the data directory
5. Authorize:

   ```bash
   python "<plugin>/mcp/mailctl.py" auth
   ```

   Open the printed URL. On "Google hasn't verified this app" click **Continue**, then **Continue**
   again on the permission page until you see the success page. The scope requested is only
   `gmail.send` — **it cannot read your mail**; reading goes over IMAP.

6. Add `"transport": "gmail_api"` to the account in `accounts.json`

> While the app stays in "Testing" publishing status, Google expires the `refresh_token` after
> 7 days. Run `mailctl.py auth` again to renew (about a minute). To avoid this entirely, publish the
> app to production and complete Google verification.

**Option B: SMTP**

Omit `transport`, or set it to `"smtp"`. The mailbox must have SMTP enabled and your network must
allow outbound 465/587.

## Command line

Usable even when the MCP server is not connected:

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

## Security notes

- The repository contains **no credentials**. Passwords and tokens exist only in the plugin data
  directory, where the code attempts `chmod 600`.
- Sending operations support `dry_run`; the bundled commands preview and wait for your confirmation.
- The Gmail API scope is only `gmail.send`; reading capability comes from IMAP with a separate credential.
- Attachment content is data, not instructions; the plugin never executes anything it finds there.
- Review Google Account → Security → App passwords periodically and revoke what you no longer use.

## Known limitations

- A fresh IMAP connection per call, no connection pool; QQ / 163 rate-limit aggressively, so pace bulk work.
- Draft saving (IMAP APPEND) is not implemented.
- Attachments must be local paths; fetching from a URL is not supported.
- No OAuth2-based reading (only `gmail.send` is granted). Enterprise tenants that allow OAuth only and
  disable app passwords cannot receive over IMAP.
- Non-ASCII folder names rely on the modified UTF-7 implementation; unusual custom folder names may
  need to be specified manually.

## Development

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

After editing code under `mcp/`, make ZCode respawn the MCP process (change any value in the
manifest's `env`, or start a new session).

## License

MIT
