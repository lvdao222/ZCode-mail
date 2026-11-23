# -*- coding: utf-8 -*-
"""
mail_mcp.py — 极简 MCP stdio 服务器（JSON-RPC 2.0，换行分隔，无第三方依赖）
在 ZCode 里注册后，工具名为 mcp__mail__*。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mailcore as mc  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "mail", "version": "1.0.0"}

STR = {"type": "string"}
INT = {"type": "integer"}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props,
            "required": required or [], "additionalProperties": False}


TOOLS = [
    {
        "name": "mail_accounts",
        "description": "列出本机已配置的邮箱账号（不返回密码）以及默认账号。",
        "inputSchema": _obj({}),
    },
    {
        "name": "mail_check",
        "description": "自检账号连通性：IMAP 登录 + SMTP 登录，返回收件箱总数/未读数；可选发一封测试邮件。",
        "inputSchema": _obj({
            "account": STR, "test_send_to": STR,
        }),
    },
    {
        "name": "mail_folders",
        "description": "列出邮箱文件夹（INBOX、已发送、草稿等）。",
        "inputSchema": _obj({"account": STR}),
    },
    {
        "name": "mail_list",
        "description": "列出某文件夹最近的邮件（默认 INBOX，10 封，新→旧）。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"},
            "limit": {**INT, "default": 10}, "unread_only": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "mail_search",
        "description": "IMAP 搜索邮件。query 支持 from:x@y.com / subject:关键词 / since:01-Jan-2026 / before: / text: / 未读 等，空格分隔多个条件。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"},
            "query": STR, "limit": {**INT, "default": 20},
        }, ["query"]),
    },
    {
        "name": "mail_read",
        "description": "按 UID 读取一封邮件全文（文本正文 + HTML 正文 + 附件清单）。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"},
            "uid": STR, "mark_seen": {"type": "boolean", "default": False},
        }, ["uid"]),
    },
    {
        "name": "mail_send",
        "description": "发送邮件。to 可为字符串或数组；attachments 为本地文件路径数组；html_body 存在时发 multipart/alternative。",
        "inputSchema": _obj({
            "account": STR, "to": {"type": ["string", "array"], "items": STR},
            "subject": STR, "body": STR, "cc": {"type": ["string", "array"], "items": STR},
            "bcc": {"type": ["string", "array"], "items": STR}, "html_body": STR,
            "attachments": {"type": "array", "items": STR},
            "dry_run": {"type": "boolean", "default": False},
        }, ["to", "subject"]),
    },
    {
        "name": "mail_reply",
        "description": "回复某封邮件（自动 Re: 主题、In-Reply-To/References，可带引用原文）。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"}, "uid": STR,
            "body": STR, "reply_all": {"type": "boolean", "default": False},
            "html_body": STR, "attachments": {"type": "array", "items": STR},
            "quote": {"type": "boolean", "default": True},
            "dry_run": {"type": "boolean", "default": False},
        }, ["uid", "body"]),
    },
    {
        "name": "mail_attachment",
        "description": "把某封邮件的第 index 个附件保存到本地目录。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"}, "uid": STR,
            "index": {**INT, "default": 0}, "save_dir": STR,
        }, ["uid"]),
    },
    {
        "name": "mail_flag",
        "description": "修改邮件标记：add/remove 支持 \\\\Seen \\\\Flagged \\\\Answered \\\\Deleted。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"}, "uid": STR,
            "add": {"type": "array", "items": STR},
            "remove": {"type": "array", "items": STR},
        }, ["uid"]),
    },
    {
        "name": "mail_move",
        "description": "把邮件移动/删除到指定文件夹（如 Trash、已删除）。",
        "inputSchema": _obj({
            "account": STR, "folder": {**STR, "default": "INBOX"}, "uid": STR,
            "dest": STR,
        }, ["uid", "dest"]),
    },
]


def dispatch(name: str, a: dict):
    if name == "mail_accounts":
        cfg = mc.load_config()
        return {"config_file": str(mc.config_path()),
                "default_account": cfg.get("default_account"),
                "accounts": [{"name": k, "address": v.get("address"),
                              "imap": v.get("imap_host"), "smtp": v.get("smtp_host")}
                             for k, v in (cfg.get("accounts") or {}).items()]}
    if name == "mail_check":
        return mc.check_account(a.get("account"), a.get("test_send_to"))
    if name == "mail_folders":
        return mc.list_folders(a.get("account"))
    if name == "mail_list":
        return mc.list_messages(a.get("account"), a.get("folder") or "INBOX",
                                int(a.get("limit", 10)), bool(a.get("unread_only")))
    if name == "mail_search":
        return mc.search_messages(a.get("account"), a.get("folder") or "INBOX",
                                  a.get("query", ""), int(a.get("limit", 20)))
    if name == "mail_read":
        return mc.read_message(a.get("account"), a.get("folder") or "INBOX",
                               a["uid"], bool(a.get("mark_seen")))
    if name == "mail_send":
        return mc.send_mail(a.get("account"), a.get("to"), a.get("subject", ""),
                            a.get("body", ""), a.get("cc"), a.get("bcc"),
                            a.get("html_body"), a.get("attachments"),
                            dry_run=bool(a.get("dry_run")))
    if name == "mail_reply":
        return mc.reply_mail(a.get("account"), a.get("folder") or "INBOX", a["uid"],
                             a.get("body", ""), bool(a.get("reply_all")),
                             a.get("html_body"), a.get("attachments"),
                             bool(a.get("quote", True)), bool(a.get("dry_run")))
    if name == "mail_attachment":
        return mc.save_attachment(a.get("account"), a.get("folder") or "INBOX",
                                  a["uid"], int(a.get("index", 0)),
                                  a.get("save_dir") or ".")
    if name == "mail_flag":
        return mc.set_flags(a.get("account"), a.get("folder") or "INBOX", a["uid"],
                            a.get("add"), a.get("remove"))
    if name == "mail_move":
        return mc.move_message(a.get("account"), a.get("folder") or "INBOX",
                               a["uid"], a["dest"])
    raise mc.MailError(f"未知工具 {name}")


def _send(obj: dict):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _log(msg: str):
    sys.stderr.write(f"[mail-mcp] {msg}\n")
    sys.stderr.flush()


def handle(req: dict):
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }}
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            data = dispatch(name, args)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": json.dumps(data, ensure_ascii=False, indent=2, default=str)}],
                "isError": False}}
        except Exception as e:  # noqa: BLE001
            _log(f"tool {name} failed: {e}")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True}}
    if method in ("shutdown", "exit"):
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    _log(f"started, config={mc.config_path()}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"bad json: {e}")
            continue
        try:
            resp = handle(req)
        except Exception:  # noqa: BLE001
            _log(traceback.format_exc())
            resp = {"jsonrpc": "2.0", "id": req.get("id"),
                    "error": {"code": -32603, "message": "internal error"}}
        if resp is not None:
            _send(resp)
        if req.get("method") == "exit":
            break


if __name__ == "__main__":
    main()
