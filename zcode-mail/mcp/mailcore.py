# -*- coding: utf-8 -*-
"""
mailcore.py — IMAP/SMTP 收发邮件核心库（纯标准库，零依赖）
供 mail_mcp.py (MCP stdio 服务) 与 mailctl.py (命令行) 共用。
"""
from __future__ import annotations

import email
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import ssl
from email import policy
from email.header import decode_header, Header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr, parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "accounts.json"
# 旧版（裸 MCP 时期）的数据目录：插件首次运行时会从这里迁移凭据
LEGACY_DIR = Path.home() / ".zcode" / "tools" / "mail-mcp"
DATA_FILES = ("accounts.json", "oauth_client.json", "token.json")


# ---------------------------------------------------------------- config

def data_dir() -> Path:
    """数据目录：MAIL_MCP_CONFIG 所在目录；未设置则回落到旧版本地目录。

    兼容插件变量未被替换的情况（路径里残留 `${...}`）。
    """
    env = os.environ.get("MAIL_MCP_CONFIG")
    if env and "${" not in env:
        return Path(env).expanduser().parent
    return LEGACY_DIR


def data_file(name: str) -> Path:
    return data_dir() / name


def ensure_data_dir() -> Path:
    """确保数据目录存在，并把旧目录里的凭据搬过去（只补缺失的文件）。"""
    import shutil
    d = data_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        return LEGACY_DIR
    if d != LEGACY_DIR:
        for name in DATA_FILES:
            src, dst = LEGACY_DIR / name, d / name
            if src.exists() and not dst.exists():
                try:
                    shutil.copy2(src, dst)
                    if name in ("accounts.json", "token.json", "oauth_client.json"):
                        try:
                            os.chmod(dst, 0o600)
                        except Exception:
                            pass
                except OSError:
                    pass
    return d


def config_path() -> Path:
    ensure_data_dir()
    return data_file("accounts.json")


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {"accounts": {}, "default_account": None}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("accounts", {})
    return data


def get_account(name: str | None = None) -> dict:
    cfg = load_config()
    accounts = cfg.get("accounts") or {}
    if not accounts:
        raise MailError(
            f"没有配置邮箱账号。请在 {config_path()} 里填写 accounts（参考 accounts.example.json），"
            "或先运行 mailctl.py add 生成模板。"
        )
    key = name or cfg.get("default_account") or next(iter(accounts))
    if key not in accounts:
        raise MailError(f"账号 {key!r} 不存在，已配置：{list(accounts)}")
    acct = dict(accounts[key])
    acct["name"] = key
    return _normalize(acct)


class MailError(RuntimeError):
    pass


# ------------------------------------------------------------ presets

PRESETS = {
    "gmail.com": ("imap.gmail.com", 993, True, "smtp.gmail.com", 465, True),
    "googlemail.com": ("imap.gmail.com", 993, True, "smtp.gmail.com", 465, True),
    "qq.com": ("imap.qq.com", 993, True, "smtp.qq.com", 465, True),
    "foxmail.com": ("imap.qq.com", 993, True, "smtp.qq.com", 465, True),
    "163.com": ("imap.163.com", 993, True, "smtp.163.com", 465, True),
    "126.com": ("imap.126.com", 993, True, "smtp.126.com", 465, True),
    "yeah.net": ("imap.yeah.net", 993, True, "smtp.yeah.net", 465, True),
    "sina.com": ("imap.sina.com", 993, True, "smtp.sina.com", 465, True),
    "aliyun.com": ("imap.aliyun.com", 993, True, "smtp.aliyun.com", 465, True),
    "outlook.com": ("outlook.office365.com", 993, True, "smtp.office365.com", 587, False),
    "hotmail.com": ("outlook.office365.com", 993, True, "smtp.office365.com", 587, False),
    "live.com": ("outlook.office365.com", 993, True, "smtp.office365.com", 587, False),
    "office365.com": ("outlook.office365.com", 993, True, "smtp.office365.com", 587, False),
    "icloud.com": ("imap.mail.me.com", 993, True, "smtp.mail.me.com", 587, False),
    "yahoo.com": ("imap.mail.yahoo.com", 993, True, "smtp.mail.yahoo.com", 465, True),
}


def preset_for(address: str) -> dict:
    domain = address.rsplit("@", 1)[-1].lower() if "@" in address else ""
    if domain not in PRESETS:
        raise MailError(
            f"未知邮箱域 {domain!r}，请手动填写 imap_host/imap_port/smtp_host/smtp_port。"
            f"内置预设：{sorted(PRESETS)}"
        )
    ih, ip, issl, sh, sp, sssl = PRESETS[domain]
    return {
        "imap_host": ih, "imap_port": ip, "imap_ssl": issl,
        "smtp_host": sh, "smtp_port": sp, "smtp_ssl": sssl,
    }


def _normalize(acct: dict) -> dict:
    a = dict(acct)
    a.setdefault("username", a.get("address", ""))
    a.setdefault("display_name", "")
    # 密码可直接写，也可用环境变量名（推荐）
    if not a.get("password") and a.get("password_env"):
        a["password"] = os.environ.get(a["password_env"], "")
    if not a.get("password"):
        raise MailError(f"账号 {a.get('name')!r} 缺少 password / password_env")
    if not a.get("imap_host") or not a.get("smtp_host"):
        a.update(preset_for(a.get("address", "")))
    a.setdefault("imap_port", 993)
    a.setdefault("imap_ssl", True)
    a.setdefault("smtp_port", 465)
    a.setdefault("smtp_ssl", True)
    a.setdefault("smtp_starttls", not a["smtp_ssl"])
    a.setdefault("sent_folder", None)
    return a


# --------------------------------------------------------- imap utf-7

def imap_utf7_encode(s: str) -> str:
    """RFC 3501 modified UTF-7，用于中文文件夹名。"""
    out, buf = [], []
    def flush():
        if buf:
            import base64
            b = base64.b64encode("".join(buf).encode("utf-16-be")).decode()
            out.append("&" + b.rstrip("=").replace("/", ",") + "-")
            buf.clear()
    for ch in s:
        if 0x20 <= ord(ch) <= 0x7E:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


def folder_arg(folder: str) -> str:
    if folder is None:
        return "INBOX"
    return imap_utf7_encode(folder) if any(ord(c) > 127 for c in folder) else folder


# --------------------------------------------------------------- imap

def _imap_connect(acct: dict) -> imaplib.IMAP4:
    try:
        if acct.get("imap_ssl", True):
            conn = imaplib.IMAP4_SSL(acct["imap_host"], int(acct["imap_port"]),
                                     ssl_context=ssl.create_default_context())
        else:
            conn = imaplib.IMAP4(acct["imap_host"], int(acct["imap_port"]))
            conn.starttls(ssl_context=ssl.create_default_context())
        conn.login(acct["username"], acct["password"])
    except imaplib.IMAP4.error as e:
        raise MailError(f"IMAP 登录失败（{acct['imap_host']}）：{e}. "
                        "国内邮箱通常需要「授权码/应用专用密码」而不是网页登录密码。") from e
    # 163/126/yeah 必须发 ID，否则 SELECT 报 Unsafe Login
    if acct["imap_host"].endswith(("163.com", "126.com", "yeah.net")):
        try:
            conn._simple_command(
                "ID", '("name" "zcode-mail" "version" "1.0" "vendor" "local-zcode")')
        except Exception:
            pass
    return conn


def _decode(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    parts = decode_header(raw)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            for e in (enc, "utf-8", "gb18030", "latin-1"):
                if not e:
                    continue
                try:
                    out.append(txt.decode(e))
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                out.append(txt.decode("utf-8", "replace"))
        else:
            out.append(txt)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def list_folders(account: str | None = None) -> list[dict]:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        typ, data = conn.list()
        out = []
        for line in data or []:
            if not isinstance(line, bytes):
                continue
            m = re.match(rb'\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]*)"\s+(?P<name>.*)', line)
            if not m:
                continue
            name = m.group("name").decode("utf-8", "replace").strip().strip('"')
            out.append({"name": _decode_folder(name), "raw": name,
                        "flags": m.group("flags").decode()})
        return out
    finally:
        _imap_quit(conn)


def _decode_folder(raw: str) -> str:
    """modified UTF-7 -> str（失败则原样返回）"""
    try:
        import base64
        def rep(m):
            b = m.group(1)
            b = b.replace(",", "/")
            b += "=" * (-len(b) % 4)
            return base64.b64decode(b).decode("utf-16-be")
        return re.sub(r"&([^-]*)-", rep, raw).replace("&-", "&")
    except Exception:
        return raw


def _imap_quit(conn):
    try:
        conn.logout()
    except Exception:
        pass


def _select(conn, folder: str):
    typ, data = conn.select(folder_arg(folder), readonly=False)
    if typ != "OK":
        raise MailError(f"无法打开文件夹 {folder!r}：{data}")


def list_messages(account: str | None = None, folder: str = "INBOX",
                  limit: int = 10, unread_only: bool = False) -> list[dict]:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        typ, data = conn.uid("SEARCH", None, "UNSEEN" if unread_only else "ALL")
        if typ != "OK":
            raise MailError(f"SEARCH 失败：{data}")
        uids = (data[0] or b"").split()
        uids = uids[-int(limit):]
        out = []
        for uid in uids:
            out.append(_fetch_header(conn, uid))
        out.reverse()  # 新 -> 旧
        return out
    finally:
        _imap_quit(conn)


def _fetch_header(conn, uid: bytes) -> dict:
    typ, data = conn.uid(
        "FETCH", uid,
        "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID)])")
    meta, raw = b"", b""
    if typ == "OK":
        for item in data or []:
            if isinstance(item, tuple):
                meta, raw = item[0], item[1]
    msg = email.message_from_bytes(raw or b"", policy=policy.default)
    flags = re.search(rb"FLAGS \(([^)]*)\)", meta or b"")
    flag_txt = flags.group(1).decode() if flags else ""
    return {
        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
        "subject": _decode(msg.get("Subject", "")),
        "from": _decode(msg.get("From", "")),
        "to": _decode(msg.get("To", "")),
        "date": _decode(msg.get("Date", "")),
        "message_id": (msg.get("Message-ID") or "").strip(),
        "seen": "\\Seen" in flag_txt,
        "flagged": "\\Flagged" in flag_txt,
        "flags": flag_txt,
    }


SEARCH_KEYS = {"from", "to", "cc", "bcc", "subject", "body", "text", "since",
               "before", "on", "sentbefore", "sentsince", "larger", "smaller",
               "unseen", "seen", "flagged", "unflagged", "answered", "deleted"}


def _build_search(query: str | None) -> list[str]:
    """支持: 'from:a@b.com subject:发票 since:01-Jan-2026 未读' 这类写法。"""
    if not query:
        return ["ALL"]
    parts: list[str] = []
    for tok in re.findall(r'(?:[^\s"]+|"[^"]*")+', query):
        tok = tok.strip('"')
        if not tok:
            continue
        if tok in ("未读", "unread"):
            parts += ["UNSEEN"]
            continue
        if tok in ("已读", "read"):
            parts += ["SEEN"]
            continue
        if ":" in tok:
            k, v = tok.split(":", 1)
            k = k.lower()
            if k in SEARCH_KEYS:
                if k in ("unseen", "seen", "flagged", "unflagged", "answered", "deleted"):
                    parts += [k.upper()]
                else:
                    key = "TEXT" if k == "body" else k.upper()
                    parts += [key, _imap_quote(v)]
                continue
        parts += ["TEXT", _imap_quote(tok)]
    return parts or ["ALL"]


def _imap_quote(v: str) -> str:
    if any(ord(c) > 127 for c in v):
        # 非 ASCII 需要 CHARSET UTF-8 前缀，由调用处处理
        return '"%s"' % v.replace('"', '\\"')
    return '"%s"' % v.replace('"', '\\"')


def search_messages(account: str | None = None, folder: str = "INBOX",
                    query: str = "", limit: int = 20) -> list[dict]:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        args = _build_search(query)
        nonascii = any(ord(c) > 127 for a in args for c in a)
        try:
            typ, data = conn.uid("SEARCH", "UTF-8" if nonascii else None, *args)
        except imaplib.IMAP4.error:
            typ, data = conn.uid("SEARCH", None, *args)
        if typ != "OK":
            raise MailError(f"SEARCH 失败：{data}")
        uids = (data[0] or b"").split()[-int(limit):]
        res = [_fetch_header(conn, u) for u in uids]
        res.reverse()
        return res
    finally:
        _imap_quit(conn)


def read_message(account: str | None = None, folder: str = "INBOX",
                 uid: str | int = "", mark_seen: bool = False,
                 max_body: int = 20000) -> dict:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        typ, data = conn.uid("FETCH", str(uid), "(FLAGS BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            raise MailError(f"读取邮件失败：uid={uid}")
        meta, raw = data[0][0], data[0][1]
        msg = email.message_from_bytes(raw, policy=policy.default)
        body_text, body_html, atts = "", "", []
        idx = 0
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            disp = (part.get_content_disposition() or "")
            fname = part.get_filename()
            if fname or disp == "attachment":
                payload = part.get_payload(decode=True) or b""
                atts.append({"index": idx, "filename": _decode(fname or f"attachment-{idx}"),
                             "content_type": ctype, "size": len(payload)})
                idx += 1
                continue
            if ctype == "text/plain" and not body_text:
                body_text = _part_text(part)
            elif ctype == "text/html" and not body_html:
                body_html = _part_text(part)
        if not body_text and body_html:
            body_text = re.sub(r"<[^>]+>", " ", body_html)
            body_text = re.sub(r"\s+", " ", body_text).strip()
        flags = re.search(rb"FLAGS \(([^)]*)\)", meta or b"")
        return {
            "uid": str(uid),
            "subject": _decode(msg.get("Subject", "")),
            "from": _decode(msg.get("From", "")),
            "to": _decode(msg.get("To", "")),
            "cc": _decode(msg.get("Cc", "")),
            "date": _decode(msg.get("Date", "")),
            "message_id": (msg.get("Message-ID") or "").strip(),
            "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
            "references": (msg.get("References") or "").strip(),
            "flags": flags.group(1).decode() if flags else "",
            "body_text": body_text[:max_body],
            "body_html": body_html[:max_body],
            "attachments": atts,
        }
    finally:
        if mark_seen and str(uid):
            try:
                conn2 = _imap_connect(acct)
                _select(conn2, folder)
                conn2.uid("STORE", str(uid), "+FLAGS", "(\\Seen)")
                _imap_quit(conn2)
            except Exception:
                pass
        _imap_quit(conn)


def _part_text(part) -> str:
    try:
        return part.get_content()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, "replace")
        except LookupError:
            return payload.decode("utf-8", "replace")


def save_attachment(account: str | None = None, folder: str = "INBOX",
                    uid: str | int = "", index: int = 0,
                    save_dir: str = ".") -> dict:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        typ, data = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if typ != "OK" or not isinstance(data[0], tuple):
            raise MailError(f"读取邮件失败：uid={uid}")
        msg = email.message_from_bytes(data[0][1], policy=policy.default)
        i = 0
        for part in msg.walk():
            if part.is_multipart():
                continue
            fname = part.get_filename()
            if not (fname or part.get_content_disposition() == "attachment"):
                continue
            if i == int(index):
                out = Path(save_dir)
                out.mkdir(parents=True, exist_ok=True)
                target = out / _safe_name(_decode(fname or f"attachment-{i}"))
                target.write_bytes(part.get_payload(decode=True) or b"")
                return {"saved": str(target), "size": target.stat().st_size}
            i += 1
        raise MailError(f"附件 index={index} 不存在，共 {i} 个")
    finally:
        _imap_quit(conn)


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name) or "attachment"


def set_flags(account: str | None = None, folder: str = "INBOX",
              uid: str | int = "", add: list[str] | None = None,
              remove: list[str] | None = None) -> dict:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        if add:
            conn.uid("STORE", str(uid), "+FLAGS", "(" + " ".join(add) + ")")
        if remove:
            conn.uid("STORE", str(uid), "-FLAGS", "(" + " ".join(remove) + ")")
        return {"uid": str(uid), "added": add or [], "removed": remove or []}
    finally:
        _imap_quit(conn)


def move_message(account: str | None = None, folder: str = "INBOX",
                 uid: str | int = "", dest: str = "Trash") -> dict:
    acct = get_account(account)
    conn = _imap_connect(acct)
    try:
        _select(conn, folder)
        typ, data = conn.uid("COPY", str(uid), folder_arg(dest))
        if typ != "OK":
            raise MailError(f"COPY 到 {dest!r} 失败：{data}")
        conn.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")
        conn.expunge()
        return {"moved": str(uid), "to": dest}
    finally:
        _imap_quit(conn)


# --------------------------------------------------------------- smtp

def _smtp_connect(acct: dict) -> smtplib.SMTP:
    try:
        if acct.get("smtp_ssl", True):
            s = smtplib.SMTP_SSL(acct["smtp_host"], int(acct["smtp_port"]),
                                 context=ssl.create_default_context(), timeout=30)
        else:
            s = smtplib.SMTP(acct["smtp_host"], int(acct["smtp_port"]), timeout=30)
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
        s.login(acct["username"], acct["password"])
        return s
    except smtplib.SMTPAuthenticationError as e:
        raise MailError(f"SMTP 认证失败（{acct['smtp_host']}）：{e}. "
                        "请确认用的是授权码/应用密码，且该邮箱已开启 SMTP 服务。") from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"SMTP 连接失败（{acct['smtp_host']}:{acct['smtp_port']}）：{e}") from e


def _addr_list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        v = [x for x in re.split(r"[,;]", v) if x.strip()]
    return [parseaddr(str(x))[1] or str(x) for x in v]


def send_mail(account: str | None = None, to="", subject: str = "", body: str = "",
              cc=None, bcc=None, html_body: str | None = None,
              attachments: list[str] | None = None,
              in_reply_to: str | None = None, references: str | None = None,
              dry_run: bool = False) -> dict:
    acct = get_account(account)
    to_l, cc_l, bcc_l = _addr_list(to), _addr_list(cc), _addr_list(bcc)
    if not to_l:
        raise MailError("收件人 to 为空")
    msg = EmailMessage()
    msg["From"] = formataddr((acct.get("display_name") or "", acct["address"]))
    msg["To"] = ", ".join(to_l)
    if cc_l:
        msg["Cc"] = ", ".join(cc_l)
    msg["Subject"] = Header(subject or "(无主题)", "utf-8").encode()
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=acct["address"].rsplit("@", 1)[-1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to
    if html_body:
        msg.set_content(body or re.sub(r"<[^>]+>", " ", html_body).strip())
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(body or "")
    for path in attachments or []:
        p = Path(path).expanduser()
        if not p.exists():
            raise MailError(f"附件不存在：{p}")
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name)
    if dry_run:
        return {"dry_run": True, "to": to_l, "cc": cc_l, "bcc": bcc_l,
                "subject": subject, "size": len(bytes(msg))}

    transport = (acct.get("transport") or "smtp").lower()
    if transport in ("gmail_api", "gmail-api", "api"):
        import gmail_api  # 延迟导入，避免循环依赖
        res = gmail_api.send_raw(bytes(msg))
        return {"sent": True, "via": "gmail_api", "from": acct["address"],
                "to": to_l, "cc": cc_l, "bcc": bcc_l, "subject": subject,
                "message_id": msg["Message-ID"],
                "gmail_id": res.get("id"), "gmail_thread": res.get("threadId"),
                "labels": res.get("labelIds")}

    s = _smtp_connect(acct)
    try:
        s.send_message(msg, from_addr=acct["address"], to_addrs=to_l + cc_l + bcc_l)
    finally:
        try:
            s.quit()
        except Exception:
            pass
    return {"sent": True, "from": acct["address"], "to": to_l, "cc": cc_l,
            "bcc": bcc_l, "subject": subject, "message_id": msg["Message-ID"]}


def reply_mail(account: str | None = None, folder: str = "INBOX",
               uid: str | int = "", body: str = "", reply_all: bool = False,
               html_body: str | None = None, attachments: list[str] | None = None,
               quote: bool = True, dry_run: bool = False) -> dict:
    acct = get_account(account)
    orig = read_message(account, folder, uid)
    me = {acct["address"].lower(), (acct.get("username") or "").lower()}
    to = [parseaddr(orig["from"])[1]]
    cc = []
    if reply_all:
        for a in _addr_list(orig["to"]) + _addr_list(orig["cc"]):
            if a.lower() not in me and a not in to:
                cc.append(a)
    subj = orig["subject"] if orig["subject"].lower().startswith("re:") else f"Re: {orig['subject']}"
    text = body
    if quote:
        q = "\n".join("> " + l for l in orig["body_text"].splitlines()[:60])
        text = f"{body}\n\n--- 原邮件（{orig['from']} / {orig['date']}）---\n{q}"
    return send_mail(account=account, to=to, cc=cc, subject=subj, body=text,
                     html_body=html_body, attachments=attachments,
                     in_reply_to=orig["message_id"], references=orig["references"],
                     dry_run=dry_run)


def check_account(account: str | None = None, test_send_to: str | None = None) -> dict:
    acct = get_account(account)
    out = {"account": acct["name"], "address": acct["address"],
           "imap": f"{acct['imap_host']}:{acct['imap_port']}",
           "smtp": f"{acct['smtp_host']}:{acct['smtp_port']}"}
    conn = _imap_connect(acct)
    try:
        typ, data = conn.select("INBOX")
        typ2, d2 = conn.uid("SEARCH", None, "ALL")
        out["imap_ok"] = True
        out["inbox_total"] = len((d2[0] or b"").split()) if typ2 == "OK" else None
        typ3, d3 = conn.uid("SEARCH", None, "UNSEEN")
        out["inbox_unread"] = len((d3[0] or b"").split()) if typ3 == "OK" else None
    finally:
        _imap_quit(conn)
    transport = (acct.get("transport") or "smtp").lower()
    if transport in ("gmail_api", "gmail-api", "api"):
        try:
            import gmail_api
            st = gmail_api.token_status()
            out["smtp_ok"] = bool(st.get("authorized"))
            out["transport"] = "gmail_api"
            out["token"] = st
            if not st.get("authorized"):
                out["hint"] = ("Gmail API 未授权：运行 python gmail_api.py auth "
                               "或 python mailctl.py auth")
        except Exception as e:  # noqa: BLE001
            out["smtp_ok"] = False
            out["transport"] = "gmail_api"
            out["token_error"] = f"{type(e).__name__}: {e}"
        if test_send_to:
            out["test_send"] = send_mail(account, to=test_send_to,
                                         subject="ZCode 邮件通道自检",
                                         body="这是一封由 ZCode 本地邮件通道发出的测试邮件。")
        return out

    s = _smtp_connect(acct)
    try:
        s.noop()
        out["smtp_ok"] = True
    finally:
        try:
            s.quit()
        except Exception:
            pass
    if test_send_to:
        out["test_send"] = send_mail(account, to=test_send_to,
                                     subject="ZCode 邮件通道自检",
                                     body="这是一封由 ZCode 本地邮件 MCP 发出的测试邮件。")
    return out
