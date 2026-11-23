# -*- coding: utf-8 -*-
"""
mailctl.py — 命令行收发邮件（MCP 未重载时也能直接用）
用法：
  python mailctl.py accounts
  python mailctl.py add myname --address me@qq.com --password-env MAIL_PASS
  python mailctl.py check [--account myname] [--test-to x@y.com]
  python mailctl.py folders
  python mailctl.py list   --folder INBOX --limit 10 [--unread]
  python mailctl.py search --query "from:a@b.com subject:发票" --limit 20
  python mailctl.py read   --uid 123 [--folder INBOX] [--mark-seen]
  python mailctl.py send   --to a@b.com --subject 主题 --body 正文 [--attach f1 f2] [--html file.html] [--dry-run]
  python mailctl.py reply  --uid 123 --body 回复内容 [--reply-all] [--dry-run]
  python mailctl.py attach --uid 123 --index 0 --dir ./downloads
  python mailctl.py flag   --uid 123 --add \\Seen --remove \\Flagged
  python mailctl.py move   --uid 123 --dest Trash
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mailcore as mc  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_accounts(a):
    cfg = mc.load_config()
    out({"config_file": str(mc.config_path()),
         "exists": mc.config_path().exists(),
         "default_account": cfg.get("default_account"),
         "accounts": {k: {"address": v.get("address"),
                          "imap_host": v.get("imap_host"),
                          "smtp_host": v.get("smtp_host"),
                          "has_password": bool(v.get("password") or v.get("password_env"))}
                      for k, v in (cfg.get("accounts") or {}).items()}})


def cmd_add(a):
    p = mc.config_path()
    cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"accounts": {}}
    cfg.setdefault("accounts", {})
    entry = {"address": a.address, "username": a.address, "display_name": a.display_name or ""}
    if a.password:
        entry["password"] = a.password
    elif a.password_env:
        entry["password_env"] = a.password_env
    try:
        entry.update(mc.preset_for(a.address))
    except mc.MailError as e:
        print(f"[warn] {e}", file=sys.stderr)
    cfg["accounts"][a.name] = entry
    cfg.setdefault("default_account", a.name)
    if a.make_default:
        cfg["default_account"] = a.name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {p}（账号 {a.name}）。密码建议用 password_env 指向环境变量，避免明文落盘。")


def cmd_check(a):
    out(mc.check_account(a.account, a.test_to))


def cmd_folders(a):
    out(mc.list_folders(a.account))


def cmd_list(a):
    out(mc.list_messages(a.account, a.folder, a.limit, a.unread))


def cmd_search(a):
    out(mc.search_messages(a.account, a.folder, a.query, a.limit))


def cmd_read(a):
    out(mc.read_message(a.account, a.folder, a.uid, a.mark_seen))


def cmd_send(a):
    html = Path(a.html).read_text(encoding="utf-8") if a.html else None
    out(mc.send_mail(a.account, a.to, a.subject, a.body, a.cc, a.bcc,
                     html, a.attach, dry_run=a.dry_run))


def cmd_reply(a):
    html = Path(a.html).read_text(encoding="utf-8") if a.html else None
    out(mc.reply_mail(a.account, a.folder, a.uid, a.body, a.reply_all,
                      html, a.attach, not a.no_quote, a.dry_run))


def cmd_attach(a):
    out(mc.save_attachment(a.account, a.folder, a.uid, a.index, a.dir))


def cmd_flag(a):
    out(mc.set_flags(a.account, a.folder, a.uid, a.add, a.remove))


def cmd_move(a):
    out(mc.move_message(a.account, a.folder, a.uid, a.dest))


def cmd_auth(a):
    import gmail_api
    if a.status:
        out(gmail_api.token_status())
        return
    res = gmail_api.authorize(a.port, a.email or (mc.get_account(a.account)["address"]),
                             a.timeout, a.url_out)
    out(res)


def cmd_token(a):
    import gmail_api
    if a.refresh:
        t = gmail_api.access_token(force_refresh=True)
        out({"refreshed": True, "prefix": t[:12] + "..."})
    else:
        out(gmail_api.token_status())


def main():
    p = argparse.ArgumentParser(description="ZCode 本地邮件 CLI（IMAP/SMTP）")
    p.add_argument("--account", help="账号别名，默认用 default_account")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("accounts", help="列出账号")
    s.set_defaults(func=cmd_accounts)

    s = sub.add_parser("add", help="新增账号")
    s.add_argument("name")
    s.add_argument("--address", required=True)
    s.add_argument("--password", help="明文密码/授权码（不推荐）")
    s.add_argument("--password-env", help="存放密码的环境变量名（推荐）")
    s.add_argument("--display-name", default="")
    s.add_argument("--make-default", action="store_true")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("check", help="连通性自检")
    s.add_argument("--test-to", help="发一封测试邮件到该地址")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("folders", help="列出文件夹")
    s.set_defaults(func=cmd_folders)

    s = sub.add_parser("list", help="列出最近邮件")
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--unread", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("search", help="搜索邮件")
    s.add_argument("--query", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("read", help="读一封邮件")
    s.add_argument("--uid", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--mark-seen", action="store_true")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser("send", help="发送邮件")
    s.add_argument("--to", required=True)
    s.add_argument("--subject", default="")
    s.add_argument("--body", default="")
    s.add_argument("--cc")
    s.add_argument("--bcc")
    s.add_argument("--html", help="HTML 正文文件路径")
    s.add_argument("--attach", nargs="*", help="附件路径")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_send)

    s = sub.add_parser("reply", help="回复邮件")
    s.add_argument("--uid", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--body", required=True)
    s.add_argument("--reply-all", action="store_true")
    s.add_argument("--no-quote", action="store_true")
    s.add_argument("--html")
    s.add_argument("--attach", nargs="*")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_reply)

    s = sub.add_parser("attach", help="保存附件")
    s.add_argument("--uid", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--index", type=int, default=0)
    s.add_argument("--dir", default=".")
    s.set_defaults(func=cmd_attach)

    s = sub.add_parser("flag", help="改标记")
    s.add_argument("--uid", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--add", nargs="*")
    s.add_argument("--remove", nargs="*")
    s.set_defaults(func=cmd_flag)

    s = sub.add_parser("move", help="移动邮件")
    s.add_argument("--uid", required=True)
    s.add_argument("--folder", default="INBOX")
    s.add_argument("--dest", required=True)
    s.set_defaults(func=cmd_move)

    s = sub.add_parser("auth", help="Gmail API 首次授权（浏览器回调）")
    s.add_argument("--port", type=int)
    s.add_argument("--email")
    s.add_argument("--timeout", type=int, default=600)
    s.add_argument("--url-out")
    s.add_argument("--status", action="store_true", help="只看令牌状态")
    s.set_defaults(func=cmd_auth)

    s = sub.add_parser("token", help="查看/刷新 Gmail API 令牌")
    s.add_argument("--refresh", action="store_true")
    s.set_defaults(func=cmd_token)

    a = p.parse_args()
    try:
        a.func(a)
    except mc.MailError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
