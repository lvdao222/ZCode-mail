#!/usr/bin/env bash
#
# One-command installer for ZCode Mail (macOS / Linux).
#
# The ZCode desktop app has no end-user plugin CLI: installing a plugin is a UI flow
# (add marketplace -> open plugin -> install). This script performs the same steps from
# the command line: download repo -> register a local directory marketplace -> register
# the plugin -> enable it in config.json. Every state file it touches is backed up first.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --remove-legacy-mcp
#   ./install.sh --uninstall
#
set -euo pipefail

REPO="${REPO:-lvdao222/ZCode-mail}"
BRANCH="${BRANCH:-main}"
MARKET_ID="${MARKET_ID:-zcode-mail-github}"
PLUGIN_NAME="${PLUGIN_NAME:-zcode-mail}"
UNINSTALL=0
REMOVE_LEGACY_MCP=0

for arg in "$@"; do
  case "$arg" in
    --uninstall) UNINSTALL=1 ;;
    --remove-legacy-mcp) REMOVE_LEGACY_MCP=1 ;;
    -h|--help)
      sed -n '2,14p' "$0" 2>/dev/null || echo "see README"
      exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

ZCODE_CLI="$HOME/.zcode/cli"
PLUGINS_DIR="$ZCODE_CLI/plugins"
KNOWN="$PLUGINS_DIR/known_marketplaces.json"
INSTALLED="$PLUGINS_DIR/installed_plugins.json"
CONFIG="$ZCODE_CLI/config.json"
SRC_ROOT="$HOME/.zcode/plugin-src/$PLUGIN_NAME"
CACHE_ROOT="$PLUGINS_DIR/cache/$MARKET_ID"
PLUGIN_ID="$PLUGIN_NAME@$MARKET_ID"

if [ ! -d "$ZCODE_CLI" ]; then
  echo "error: ZCode config directory not found: $ZCODE_CLI" >&2
  echo "       install and launch the ZCode desktop app at least once first." >&2
  exit 1
fi

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import json' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "error: python3 is required (the plugin's MCP server runs on Python)." >&2
  exit 1
fi

echo
echo "=== ZCode Mail installer ==="
echo "    config dir: $ZCODE_CLI"
echo "    python:     $($PY -V 2>&1)"

# ------------------------------------------------------------------ uninstall
if [ "$UNINSTALL" = "1" ]; then
  echo
  echo "[uninstall] $PLUGIN_ID"
  "$PY" - "$KNOWN" "$INSTALLED" "$CONFIG" "$MARKET_ID" "$PLUGIN_ID" <<'PYEOF'
import json, os, shutil, sys, time

known_p, installed_p, config_p, market_id, plugin_id = sys.argv[1:6]
stamp = time.strftime("%Y%m%d%H%M%S")

def load(p, default):
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(p, data):
    if os.path.exists(p):
        bak = f"{p}.bak-zcode-mail-{stamp}"
        shutil.copy2(p, bak)
        print(f"    backup: {bak}")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

inst = load(installed_p, None)
if inst and isinstance(inst.get("plugins"), list):
    before = len(inst["plugins"])
    inst["plugins"] = [p for p in inst["plugins"] if p.get("id") != plugin_id]
    if len(inst["plugins"]) != before:
        save(installed_p, inst)
        print("    removed from installed_plugins.json")

known = load(known_p, None)
if known and isinstance(known.get("marketplaces"), list):
    before = len(known["marketplaces"])
    known["marketplaces"] = [m for m in known["marketplaces"] if m.get("id") != market_id]
    if len(known["marketplaces"]) != before:
        save(known_p, known)
        print("    removed from known_marketplaces.json")

cfg = load(config_p, None)
if cfg:
    ep = (cfg.get("plugins") or {}).get("enabledPlugins") or {}
    if plugin_id in ep:
        bak = f"{config_p}.bak-zcode-mail-{stamp}"
        shutil.copy2(config_p, bak)
        print(f"    backup: {bak}")
        del ep[plugin_id]
        cfg["plugins"]["enabledPlugins"] = ep
        with open(config_p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("    removed from config.json enabledPlugins")
PYEOF

  for d in "$CACHE_ROOT" "$SRC_ROOT"; do
    if [ -d "$d" ]; then rm -rf "$d"; echo "    deleted: $d"; fi
  done
  echo
  echo "Uninstalled. Restart ZCode to apply. Credentials are left untouched."
  exit 0
fi

# ------------------------------------------------------------------ download
TMP="$(mktemp -d "${TMPDIR:-/tmp}/zcode-mail-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
URL="https://codeload.github.com/$REPO/zip/refs/heads/$BRANCH"

echo
echo "[1/4] download $URL"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP/repo.zip"
else
  wget -q "$URL" -O "$TMP/repo.zip"
fi
unzip -q "$TMP/repo.zip" -d "$TMP"

EXTRACTED=""
for d in "$TMP"/*/; do
  if [ -f "$d/marketplace.json" ]; then EXTRACTED="${d%/}"; break; fi
done
if [ -z "$EXTRACTED" ]; then
  echo "error: marketplace.json not found in the archive; repository layout changed." >&2
  exit 1
fi
echo "    extracted: $EXTRACTED"

# ------------------------------------------------------------------ files
echo
echo "[2/4] install plugin files"
rm -rf "$SRC_ROOT"
mkdir -p "$SRC_ROOT"
cp -R "$EXTRACTED"/. "$SRC_ROOT"/
rm -rf "$SRC_ROOT/.git"

# never ship credentials
find "$SRC_ROOT" -type f \( -name accounts.json -o -name token.json -o -name oauth_client.json \) -delete 2>/dev/null || true

VER="$("$PY" - "$SRC_ROOT/marketplace.json" "$PLUGIN_NAME" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
name = sys.argv[2]
for p in data.get("plugins", []):
    if p.get("name") == name:
        print(p["version"]); break
PYEOF
)"
if [ -z "$VER" ]; then
  echo "error: plugin '$PLUGIN_NAME' not listed in marketplace.json." >&2
  exit 1
fi

INSTALL_PATH="$CACHE_ROOT/$PLUGIN_NAME/$VER"
rm -rf "$INSTALL_PATH"
mkdir -p "$INSTALL_PATH"
cp -R "$SRC_ROOT/$PLUGIN_NAME"/. "$INSTALL_PATH"/
# flatten if payload nested one level deeper
if [ -d "$INSTALL_PATH/$PLUGIN_NAME/.zcode-plugin" ]; then
  mv "$INSTALL_PATH/$PLUGIN_NAME"/* "$INSTALL_PATH"/ 2>/dev/null || true
  rm -rf "$INSTALL_PATH/$PLUGIN_NAME"
fi
find "$INSTALL_PATH" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "$INSTALL_PATH/mcp/"*.py 2>/dev/null || true

# prune older versions of this plugin so only the installed one remains
find "$CACHE_ROOT/$PLUGIN_NAME" -mindepth 1 -maxdepth 1 -type d ! -name "$VER" -print0 2>/dev/null |
  while IFS= read -r -d '' old; do rm -rf "$old"; echo "    pruned old version: $(basename "$old")"; done

echo "    $INSTALL_PATH"

# ------------------------------------------------------------------ state
echo
echo "[3/4] register marketplace and plugin"

"$PY" - "$KNOWN" "$INSTALLED" "$CONFIG" "$MARKET_ID" "$PLUGIN_NAME" "$PLUGIN_ID" "$VER" "$SRC_ROOT" "$INSTALL_PATH" "$REMOVE_LEGACY_MCP" <<'PYEOF'
import json, os, shutil, sys, time, uuid

(known_p, installed_p, config_p, market_id, plugin_name, plugin_id,
 version, src_root, install_path, remove_legacy) = sys.argv[1:11]
remove_legacy = remove_legacy == "1"
stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

def load(p, default):
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(p, data):
    if os.path.exists(p):
        bak = f"{p}.bak-zcode-mail-{time.strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(p, bak)
        print(f"    backup: {bak}")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

known = load(known_p, {"version": 1, "marketplaces": []})
known.setdefault("marketplaces", [])
known["marketplaces"] = [m for m in known["marketplaces"] if m.get("id") != market_id]
known["marketplaces"].append({
    "id": market_id,
    "source": {"source": "directory", "path": src_root},
    "name": market_id,
    "description": "ZCode Mail (local directory marketplace registered by install.sh)",
    "addedAt": stamp,
    "lastUpdated": stamp,
    "pluginCount": 1,
    "cacheTransactionId": str(uuid.uuid4()),
})
save(known_p, known)
print(f"    known_marketplaces.json <- {market_id}")

installed = load(installed_p, {"version": 1, "plugins": []})
installed.setdefault("plugins", [])
old = next((p for p in installed["plugins"] if p.get("id") == plugin_id), None)
installed["plugins"] = [p for p in installed["plugins"] if p.get("id") != plugin_id]
installed["plugins"].append({
    "id": plugin_id,
    "name": plugin_name,
    "marketplace": market_id,
    "version": version,
    "installPath": install_path,
    "installedAt": (old or {}).get("installedAt", stamp),
    "updatedAt": stamp,
    "scope": "user",
    "source": f"./{plugin_name}",
    "cacheTransactionId": str(uuid.uuid4()),
})
save(installed_p, installed)
print(f"    installed_plugins.json <- {plugin_id} ({version})")

cfg = load(config_p, None)
if cfg is not None:
    cfg.setdefault("plugins", {})
    ep = cfg["plugins"].get("enabledPlugins") or {}
    ep[plugin_id] = True
    cfg["plugins"]["enabledPlugins"] = ep
    if remove_legacy:
        servers = (cfg.get("mcp") or {}).get("servers") or {}
        if "mail" in servers:
            del servers["mail"]
            cfg["mcp"]["servers"] = servers
            print("    removed legacy mcp.servers.mail entry (avoids clashing with the plugin)")
    save(config_p, cfg)
    print(f"    config.json <- enabledPlugins[{plugin_id}] = true")
PYEOF

# ------------------------------------------------------------------ done
echo
echo "[4/4] done"
cat <<EOF

    plugin:     $PLUGIN_ID
    version:    $VER
    installed:  $INSTALL_PATH

Next:
    1. Fully quit ZCode and start it again (plugins and MCP servers load at startup).
    2. Settings -> Plugin Management should list ZCode Mail as enabled.
    3. Try /mail-check, or /mail-setup to configure credentials with the assistant.

Credentials (app password / OAuth token) are not shipped with the repo. Configure them
into the plugin data directory as described in README.

Uninstall: ./install.sh --uninstall

EOF
