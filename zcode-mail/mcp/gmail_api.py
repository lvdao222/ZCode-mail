# -*- coding: utf-8 -*-
"""
gmail_api.py — 走 HTTPS 443 的 Gmail API 发信通道（纯标准库，零依赖）

为什么需要它：部分网络环境会对 smtp.gmail.com 的 465/587/25 做拦截（TLS 握手超时或被掐），
但 https://gmail.googleapis.com 正常。所以发信改走 Gmail REST API。

用法：
  python gmail_api.py auth --port 8765      # 首次授权：打印授权 URL，等浏览器回调
  python gmail_api.py status                # 查看令牌状态
  python gmail_api.py send --to a@b.com --subject s --body b [--attach f]
"""
from __future__ import annotations

import argparse
import base64
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _dfile(name: str) -> Path:
    """凭据文件路径，跟随 mailcore 的数据目录解析（插件数据目录 / 旧目录）。"""
    try:
        import mailcore
        return mailcore.data_file(name)
    except Exception:  # pragma: no cover
        return HERE / name


def CLIENT_FILE() -> Path:  # noqa: N802
    return _dfile("oauth_client.json")


def TOKEN_FILE() -> Path:  # noqa: N802
    return _dfile("token.json")


class GmailApiError(RuntimeError):
    pass


# --------------------------------------------------------------- storage

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def client_info() -> dict:
    d = _read_json(CLIENT_FILE(), None)
    if not d:
        raise GmailApiError(f"缺少 {CLIENT_FILE()}（OAuth 客户端信息）")
    info = d.get("installed") or d.get("web") or d
    if not info.get("client_id") or not info.get("client_secret"):
        raise GmailApiError("oauth_client.json 缺少 client_id / client_secret")
    return info


def load_token() -> dict:
    return _read_json(TOKEN_FILE(), {})


def save_token(tok: dict):
    TOKEN_FILE().write_text(json.dumps(tok, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE(), 0o600)
    except Exception:
        pass


# ---------------------------------------------------------------- http

def _post_form(url: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise GmailApiError(f"令牌请求失败 HTTP {e.code}: {body}") from e
    except URLError_ as e:  # noqa: F821
        raise GmailApiError(f"网络错误：{e}") from e


def _api_post(url: str, token: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise GmailApiError(f"Gmail API HTTP {e.code}: {body}") from e


def _api_get(url: str, token: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise GmailApiError(f"Gmail API HTTP {e.code}: {body}") from e


# --------------------------------------------------------------- token

def access_token(force_refresh: bool = False) -> str:
    tok = load_token()
    if not tok:
        raise GmailApiError("尚未授权：先运行 python gmail_api.py auth")
    if not force_refresh and tok.get("access_token") and tok.get("expires_at", 0) > time.time() + 120:
        return tok["access_token"]
    rt = tok.get("refresh_token")
    if not rt:
        raise GmailApiError("token.json 里没有 refresh_token：需要重新运行 auth")
    ci = client_info()
    data = _post_form(TOKEN_URI, {
        "client_id": ci["client_id"], "client_secret": ci["client_secret"],
        "refresh_token": rt, "grant_type": "refresh_token",
    })
    if "access_token" not in data:
        raise GmailApiError(f"刷新失败：{data}")
    tok.update({
        "access_token": data["access_token"],
        "expires_at": time.time() + int(data.get("expires_in", 3600)),
        "scope": data.get("scope", tok.get("scope")),
    })
    save_token(tok)
    return tok["access_token"]


def token_status() -> dict:
    tok = load_token()
    if not tok:
        return {"authorized": False, "token_file": str(TOKEN_FILE())}
    return {
        "authorized": bool(tok.get("refresh_token")),
        "token_file": str(TOKEN_FILE()),
        "has_refresh_token": bool(tok.get("refresh_token")),
        "scope": tok.get("scope"),
        "access_token_expires_in": int(tok.get("expires_at", 0) - time.time()),
        "created_at": tok.get("created_at"),
        "account": tok.get("account"),
        "note": "应用若处于「测试」发布状态，refresh_token 会在 7 天后失效，需要重新 auth。",
    }


# ------------------------------------------------------------ authorize

class _Handler(http.server.BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" in qs:
            _Handler.result["code"] = qs["code"][0]
            _Handler.result["state"] = (qs.get("state") or [""])[0]
            body = "<h2>授权成功</h2><p>可以关闭本页，回到终端继续。</p>".encode("utf-8")
        else:
            _Handler.result["error"] = (qs.get("error") or ["unknown"])[0]
            body = f"<h2>授权失败</h2><pre>{urllib.parse.quote(str(_Handler.result))}</pre>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _free_port(preferred: int = 8765) -> int:
    for p in [preferred] + list(range(8766, 8800)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_auth_url(port: int, login_hint: str | None = None) -> str:
    ci = client_info()
    params = {
        "client_id": ci["client_id"],
        "redirect_uri": f"http://127.0.0.1:{port}/",
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def authorize(port: int | None = None, login_hint: str | None = None,
              timeout: int = 600, url_out: str | None = None) -> dict:
    port = port or _free_port()
    url = build_auth_url(port, login_hint)
    print(url, flush=True)
    if url_out:
        Path(url_out).write_text(url, encoding="utf-8")

    _Handler.result = {}
    with socketserver.TCPServer(("127.0.0.1", port), _Handler, bind_and_activate=False) as httpd:
        httpd.allow_reuse_address = True
        httpd.server_bind()
        httpd.server_activate()
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        deadline = time.time() + timeout
        while time.time() < deadline and not _Handler.result:
            time.sleep(0.5)
        httpd.shutdown()

    res = _Handler.result
    if not res.get("code"):
        raise GmailApiError(f"未拿到授权码：{res}")

    ci = client_info()
    data = _post_form(TOKEN_URI, {
        "code": res["code"],
        "client_id": ci["client_id"],
        "client_secret": ci["client_secret"],
        "redirect_uri": f"http://127.0.0.1:{port}/",
        "grant_type": "authorization_code",
    })
    if "refresh_token" not in data:
        raise GmailApiError(f"令牌交换失败（可能需要 prompt=consent 重新授权）：{data}")
    tok = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "scope": data.get("scope"),
        "token_type": data.get("token_type"),
        "expires_at": time.time() + int(data.get("expires_in", 3600)),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "account": login_hint,
    }
    save_token(tok)
    return {"authorized": True, "token_file": str(TOKEN_FILE()), "scope": tok["scope"]}


# ----------------------------------------------------------------- send

def send_raw(raw: bytes, token: str | None = None) -> dict:
    token = token or access_token()
    raw_b64 = base64.urlsafe_b64encode(raw).decode()
    return _api_post(SEND_URL, token, {"raw": raw_b64})


def send_message(msg, token: str | None = None) -> dict:
    return send_raw(msg.as_bytes() if hasattr(msg, "as_bytes") else msg, token)


def profile(token: str | None = None) -> dict:
    """注意：gmail.send 作用域无权读 profile，会 403；仅用于诊断。"""
    return _api_get("https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    token or access_token())


# ------------------------------------------------------------------ cli

def main():
    p = argparse.ArgumentParser(description="Gmail API (443) 发信通道")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("auth", help="首次授权")
    s.add_argument("--port", type=int)
    s.add_argument("--email", help="login_hint，预填账号")
    s.add_argument("--timeout", type=int, default=600)
    s.add_argument("--url-out", help="把授权 URL 写到文件")
    s.add_argument("--url-only", action="store_true", help="只打印 URL 不等待回调")

    s = sub.add_parser("status", help="令牌状态")
    sub.add_parser("refresh", help="强制刷新 access_token")

    s = sub.add_parser("send", help="发测试邮件")
    s.add_argument("--to", required=True)
    s.add_argument("--subject", default="ZCode 测试")
    s.add_argument("--body", default="test")
    s.add_argument("--attach", nargs="*")

    a = p.parse_args()
    if a.cmd == "auth":
        if a.url_only:
            port = a.port or _free_port()
            print(build_auth_url(port, a.email))
            return
        out = authorize(a.port, a.email, a.timeout, a.url_out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif a.cmd == "status":
        print(json.dumps(token_status(), ensure_ascii=False, indent=2))
    elif a.cmd == "refresh":
        t = access_token(force_refresh=True)
        print(json.dumps({"refreshed": True, "access_token_prefix": t[:12] + "..."}, indent=2))
    elif a.cmd == "send":
        import mailcore as mc
        r = mc.send_mail(None, a.to, a.subject, a.body, attachments=a.attach)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


try:
    URLError_ = urllib.error.URLError
except Exception:  # pragma: no cover
    URLError_ = OSError


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
