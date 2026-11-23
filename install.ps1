<#
.SYNOPSIS
    One-command installer for ZCode Mail (ZCode desktop plugin, Windows PowerShell).

.DESCRIPTION
    The ZCode desktop app has no end-user plugin CLI: installing a plugin is a UI flow
    (add marketplace -> open plugin -> install). This script performs the same steps
    from the command line:
        download repo -> register a local directory marketplace -> register the plugin
        -> enable it in config.json
    Every state file it touches is backed up first as *.bak-zcode-mail-<timestamp>.

    The script is intentionally ASCII-only so it behaves the same whether PowerShell
    reads it as UTF-8, UTF-8-with-BOM, or ANSI/GBK.

.EXAMPLE
    irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 | iex

.EXAMPLE
    # Also drop a legacy hand-written MCP entry so two "mail" servers do not compete.
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

.EXAMPLE
    .\install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$Repo = "lvdao222/ZCode-mail",
    [string]$Branch = "main",
    [string]$MarketId = "zcode-mail-github",
    [string]$PluginName = "zcode-mail",
    [switch]$Uninstall,
    [switch]$RemoveLegacyMcp
)

$ErrorActionPreference = "Stop"

function Get-ZStamp { (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ") }

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    $raw = [System.IO.File]::ReadAllText($Path)
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw | ConvertFrom-Json
}

function Write-Json([string]$Path, $Object) {
    $json = $Object | ConvertTo-Json -Depth 32
    $utf8 = New-Object System.Text.UTF8Encoding($false)   # no BOM
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $json, $utf8)
}

function Backup-Json([string]$Path) {
    if (Test-Path $Path) {
        $bak = "$Path.bak-zcode-mail-$((Get-Date).ToString('yyyyMMddHHmmss'))"
        Copy-Item $Path $bak -Force
        Write-Host "    backup: $bak" -ForegroundColor DarkGray
    }
}

$zcodeRoot = Join-Path $env:USERPROFILE ".zcode"
$zcodeCli = Join-Path $zcodeRoot "cli"
$pluginsDir = Join-Path $zcodeCli "plugins"
$knownPath = Join-Path $pluginsDir "known_marketplaces.json"
$installedPath = Join-Path $pluginsDir "installed_plugins.json"
$configPath = Join-Path $zcodeCli "config.json"
$srcRoot = Join-Path $zcodeRoot "plugin-src\$PluginName"
$cacheRoot = Join-Path $pluginsDir "cache\$MarketId"
$pluginId = "$PluginName@$MarketId"

if (-not (Test-Path $zcodeCli)) {
    throw "ZCode config directory not found: $zcodeCli. Install and launch the ZCode desktop app at least once first."
}

Write-Host ""
Write-Host "=== ZCode Mail installer ===" -ForegroundColor Cyan
Write-Host "    config dir: $zcodeCli"

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    Write-Host ""
    Write-Host "[uninstall] $pluginId" -ForegroundColor Yellow

    $installed = Read-Json $installedPath
    if ($installed -and $installed.plugins) {
        Backup-Json $installedPath
        $installed.plugins = @($installed.plugins | Where-Object { $_.id -ne $pluginId })
        Write-Json $installedPath $installed
        Write-Host "    removed from installed_plugins.json"
    }

    $known = Read-Json $knownPath
    if ($known -and $known.marketplaces) {
        Backup-Json $knownPath
        $known.marketplaces = @($known.marketplaces | Where-Object { $_.id -ne $MarketId })
        Write-Json $knownPath $known
        Write-Host "    removed from known_marketplaces.json"
    }

    $cfg = Read-Json $configPath
    if ($cfg -and $cfg.plugins -and $cfg.plugins.enabledPlugins) {
        Backup-Json $configPath
        $cfg.plugins.enabledPlugins.PSObject.Properties.Remove($pluginId)
        Write-Json $configPath $cfg
        Write-Host "    removed from config.json enabledPlugins"
    }

    foreach ($p in @($cacheRoot, $srcRoot)) {
        if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "    deleted: $p" }
    }

    Write-Host ""
    Write-Host "Uninstalled. Restart ZCode to apply. Credentials are left untouched." -ForegroundColor Green
    return
}

# ---------------------------------------------------------------- download
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("zcode-mail-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$zip = Join-Path $tmp "repo.zip"
$url = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"

Write-Host ""
Write-Host "[1/4] download $url" -ForegroundColor Yellow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$extracted = Get-ChildItem $tmp -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName "marketplace.json") } |
    Select-Object -First 1
if (-not $extracted) { throw "marketplace.json not found in the downloaded archive; repository layout changed." }
Write-Host "    extracted: $($extracted.FullName)" -ForegroundColor DarkGray

# ---------------------------------------------------------------- files
Write-Host ""
Write-Host "[2/4] install plugin files" -ForegroundColor Yellow
if (Test-Path $srcRoot) { Remove-Item $srcRoot -Recurse -Force }
New-Item -ItemType Directory -Path $srcRoot -Force | Out-Null
Copy-Item (Join-Path $extracted.FullName "*") $srcRoot -Recurse -Force

# never ship credentials even if someone committed them by accident
foreach ($s in @("accounts.json", "token.json", "oauth_client.json")) {
    Get-ChildItem $srcRoot -Recurse -Filter $s -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force }
}

$market = Read-Json (Join-Path $srcRoot "marketplace.json")
$ver = ($market.plugins | Where-Object { $_.name -eq $PluginName } | Select-Object -First 1).version
if (-not $ver) { throw "plugin '$PluginName' not listed in marketplace.json." }

$installPath = Join-Path $cacheRoot "$PluginName\$ver"
if (Test-Path $installPath) { Remove-Item $installPath -Recurse -Force }
New-Item -ItemType Directory -Path $installPath -Force | Out-Null
Copy-Item (Join-Path $srcRoot $PluginName) $installPath -Recurse -Force

# flatten: plugin payload must sit directly under the version directory
$inner = Join-Path $installPath $PluginName
if (Test-Path (Join-Path $inner ".zcode-plugin")) {
    Get-ChildItem $inner -Force | Move-Item -Destination $installPath -Force
    Remove-Item $inner -Recurse -Force
}
Get-ChildItem $installPath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force }

# prune older versions of this plugin so only the installed one remains
Get-ChildItem (Join-Path $cacheRoot $PluginName) -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne $ver } |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force; Write-Host "    pruned old version: $($_.Name)" -ForegroundColor DarkGray }

Write-Host "    $installPath" -ForegroundColor DarkGray

# ---------------------------------------------------------------- state
Write-Host ""
Write-Host "[3/4] register marketplace and plugin" -ForegroundColor Yellow
$stamp = Get-ZStamp

$known = Read-Json $knownPath
if (-not $known) { $known = [pscustomobject]@{ version = 1; marketplaces = @() } }
if (-not $known.marketplaces) {
    $known | Add-Member -NotePropertyName marketplaces -NotePropertyValue @() -Force
}
Backup-Json $knownPath
$known.marketplaces = @($known.marketplaces | Where-Object { $_.id -ne $MarketId })
$known.marketplaces += [pscustomobject]@{
    id                 = $MarketId
    source             = [pscustomobject]@{ source = "directory"; path = $srcRoot }
    name               = $MarketId
    description        = "ZCode Mail (local directory marketplace registered by install.ps1)"
    addedAt            = $stamp
    lastUpdated        = $stamp
    pluginCount        = 1
    cacheTransactionId = [guid]::NewGuid().ToString()
}
Write-Json $knownPath $known
Write-Host "    known_marketplaces.json <- $MarketId"

$installed = Read-Json $installedPath
if (-not $installed) { $installed = [pscustomobject]@{ version = 1; plugins = @() } }
if (-not $installed.plugins) {
    $installed | Add-Member -NotePropertyName plugins -NotePropertyValue @() -Force
}
Backup-Json $installedPath
$old = $installed.plugins | Where-Object { $_.id -eq $pluginId } | Select-Object -First 1
$installed.plugins = @($installed.plugins | Where-Object { $_.id -ne $pluginId })
$installed.plugins += [pscustomobject]@{
    id                 = $pluginId
    name               = $PluginName
    marketplace        = $MarketId
    version            = $ver
    installPath        = $installPath
    installedAt        = if ($old -and $old.installedAt) { $old.installedAt } else { $stamp }
    updatedAt          = $stamp
    scope              = "user"
    source             = "./$PluginName"
    cacheTransactionId = [guid]::NewGuid().ToString()
}
Write-Json $installedPath $installed
Write-Host "    installed_plugins.json <- $pluginId ($ver)"

$cfg = Read-Json $configPath
if ($cfg) {
    Backup-Json $configPath
    if (-not $cfg.plugins) {
        $cfg | Add-Member -NotePropertyName plugins -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    if (-not $cfg.plugins.enabledPlugins) {
        $cfg.plugins | Add-Member -NotePropertyName enabledPlugins -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $enabled = @{}
    foreach ($p in $cfg.plugins.enabledPlugins.PSObject.Properties) { $enabled[$p.Name] = $p.Value }
    $enabled[$pluginId] = $true
    $cfg.plugins.enabledPlugins = [pscustomobject]$enabled

    if ($RemoveLegacyMcp -and $cfg.mcp -and $cfg.mcp.servers -and $cfg.mcp.servers.PSObject.Properties["mail"]) {
        $cfg.mcp.servers.PSObject.Properties.Remove("mail")
        Write-Host "    removed legacy mcp.servers.mail entry (avoids clashing with the plugin)" -ForegroundColor DarkYellow
    }

    Write-Json $configPath $cfg
    Write-Host "    config.json <- enabledPlugins[$pluginId] = true"
}

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- done
Write-Host ""
Write-Host "[4/4] done" -ForegroundColor Green
Write-Host @"

    plugin:     $pluginId
    version:    $ver
    installed:  $installPath

Next:
    1. Fully quit ZCode and start it again (plugins and MCP servers load at startup).
    2. Settings -> Plugin Management should list ZCode Mail as enabled.
    3. Try /mail-check in a new session.

Credentials (app password / OAuth token) are not shipped with the repo. Configure them
into the plugin data directory as described in README (section "Configuration").

Uninstall: .\install.ps1 -Uninstall

"@ -ForegroundColor Gray
