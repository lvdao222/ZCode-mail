<#
.SYNOPSIS
    ZCode-mail 一行安装器（Windows PowerShell）

.DESCRIPTION
    ZCode 桌面端目前没有面向普通用户的插件命令行，官方安装走 UI：
    添加市场 -> 找到插件 -> 安装。本脚本把这三步等价地做完：
    下载仓库 -> 落一份本地目录市场 -> 写入 ZCode 的插件状态文件。

    写入前会自动备份三份状态文件（*.bak-zcode-mail-<时间戳>），
    卸载用 -Uninstall 可精确还原。

.EXAMPLE
    irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1 | iex

.EXAMPLE
    # 同时清掉旧版裸 MCP 条目，避免两个同名 mail 服务并存
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/lvdao222/ZCode-mail/main/install.ps1))) -RemoveLegacyMcp

.EXAMPLE
    # 卸载
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
    $utf8 = New-Object System.Text.UTF8Encoding($false)   # 不写 BOM
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $json, $utf8)
}

function Backup-Json([string]$Path) {
    if (Test-Path $Path) {
        $bak = "$Path.bak-zcode-mail-$((Get-Date).ToString('yyyyMMddHHmmss'))"
        Copy-Item $Path $bak -Force
        Write-Host "  备份 $bak" -ForegroundColor DarkGray
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
    throw "未找到 ZCode 配置目录：$zcodeCli。请先安装并启动过一次 ZCode 桌面端。"
}

Write-Host "`n=== ZCode Mail 安装器 ===" -ForegroundColor Cyan
Write-Host "ZCode 配置目录: $zcodeCli"

# ---------------------------------------------------------------- 卸载
if ($Uninstall) {
    Write-Host "`n[卸载] $pluginId" -ForegroundColor Yellow

    $installed = Read-Json $installedPath
    if ($installed -and $installed.plugins) {
        Backup-Json $installedPath
        $installed.plugins = @($installed.plugins | Where-Object { $_.id -ne $pluginId })
        Write-Json $installedPath $installed
        Write-Host "  已从 installed_plugins.json 移除"
    }

    $known = Read-Json $knownPath
    if ($known -and $known.marketplaces) {
        Backup-Json $knownPath
        $known.marketplaces = @($known.marketplaces | Where-Object { $_.id -ne $MarketId })
        Write-Json $knownPath $known
        Write-Host "  已从 known_marketplaces.json 移除"
    }

    $cfg = Read-Json $configPath
    if ($cfg -and $cfg.plugins -and $cfg.plugins.enabledPlugins) {
        Backup-Json $configPath
        $cfg.plugins.enabledPlugins.PSObject.Properties.Remove($pluginId)
        Write-Json $configPath $cfg
        Write-Host "  已从 config.json 的 enabledPlugins 移除"
    }

    foreach ($p in @($cacheRoot, $srcRoot)) {
        if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "  已删除 $p" }
    }

    Write-Host "`n卸载完成。重启 ZCode 生效。" -ForegroundColor Green
    return
}

# ---------------------------------------------------------------- 下载
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("zcode-mail-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$zip = Join-Path $tmp "repo.zip"
$url = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"

Write-Host "`n[1/4] 下载 $url" -ForegroundColor Yellow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$extracted = Get-ChildItem $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName "marketplace.json") } | Select-Object -First 1
if (-not $extracted) { throw "压缩包里没找到 marketplace.json，仓库结构异常。" }
Write-Host "  解压到 $($extracted.FullName)"

# ---------------------------------------------------------------- 落盘
Write-Host "`n[2/4] 安装插件文件" -ForegroundColor Yellow
if (Test-Path $srcRoot) { Remove-Item $srcRoot -Recurse -Force }
New-Item -ItemType Directory -Path $srcRoot -Force | Out-Null
Copy-Item (Join-Path $extracted.FullName "*") $srcRoot -Recurse -Force
$stray = @("accounts.json", "token.json", "oauth_client.json")
foreach ($s in $stray) {
    $bad = Get-ChildItem $srcRoot -Recurse -Filter $s -ErrorAction SilentlyContinue
    foreach ($b in $bad) { Remove-Item $b.FullName -Force }
}

$marketFile = Join-Path $srcRoot "marketplace.json"
$market = Read-Json $marketFile
$ver = ($market.plugins | Where-Object { $_.name -eq $PluginName } | Select-Object -First 1).version
if (-not $ver) { throw "marketplace.json 里找不到插件 $PluginName。" }

$installPath = Join-Path $cacheRoot "$PluginName\$ver"
if (Test-Path $installPath) { Remove-Item $installPath -Recurse -Force }
New-Item -ItemType Directory -Path $installPath -Force | Out-Null
Copy-Item (Join-Path $srcRoot $PluginName) $installPath -Recurse -Force
# 兼容：插件内容可能直接位于版本目录下
$inner = Join-Path $installPath $PluginName
if (Test-Path (Join-Path $inner ".zcode-plugin")) {
    Get-ChildItem $inner -Force | Move-Item -Destination $installPath -Force
    Remove-Item $inner -Recurse -Force
}
Get-ChildItem $installPath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
Write-Host "  $installPath" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 写状态
Write-Host "`n[3/4] 注册市场与插件" -ForegroundColor Yellow
$stamp = Get-ZStamp

$known = Read-Json $knownPath
if (-not $known) { $known = [pscustomobject]@{ version = 1; marketplaces = @() } }
if (-not $known.marketplaces) { $known | Add-Member -NotePropertyName marketplaces -NotePropertyValue @() -Force }
Backup-Json $knownPath
$known.marketplaces = @($known.marketplaces | Where-Object { $_.id -ne $MarketId })
$known.marketplaces += [pscustomobject]@{
    id                 = $MarketId
    source             = [pscustomobject]@{ source = "directory"; path = $srcRoot }
    name               = $MarketId
    description        = "ZCode Mail（由 install.ps1 注册的本地目录市场）"
    addedAt            = $stamp
    lastUpdated        = $stamp
    pluginCount        = 1
    cacheTransactionId = [guid]::NewGuid().ToString()
}
Write-Json $knownPath $known
Write-Host "  known_marketplaces.json <- $MarketId"

$installed = Read-Json $installedPath
if (-not $installed) { $installed = [pscustomobject]@{ version = 1; plugins = @() } }
if (-not $installed.plugins) { $installed | Add-Member -NotePropertyName plugins -NotePropertyValue @() -Force }
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
Write-Host "  installed_plugins.json <- $pluginId ($ver)"

$cfg = Read-Json $configPath
if ($cfg) {
    Backup-Json $configPath
    if (-not $cfg.plugins) { $cfg | Add-Member -NotePropertyName plugins -NotePropertyValue ([pscustomobject]@{}) -Force }
    if (-not $cfg.plugins.enabledPlugins) {
        $cfg.plugins | Add-Member -NotePropertyName enabledPlugins -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $enabled = @{}
    foreach ($p in $cfg.plugins.enabledPlugins.PSObject.Properties) { $enabled[$p.Name] = $p.Value }
    $enabled[$pluginId] = $true
    $cfg.plugins.enabledPlugins = [pscustomobject]$enabled

    if ($RemoveLegacyMcp -and $cfg.mcp -and $cfg.mcp.servers -and $cfg.mcp.servers.PSObject.Properties["mail"]) {
        $cfg.mcp.servers.PSObject.Properties.Remove("mail")
        Write-Host "  已移除旧版裸 MCP 条目 mcp.servers.mail（避免与插件同名冲突）" -ForegroundColor DarkYellow
    }

    Write-Json $configPath $cfg
    Write-Host "  config.json <- enabledPlugins[$pluginId] = true"
}

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 收尾
Write-Host "`n[4/4] 完成" -ForegroundColor Green
Write-Host @"

  插件:     $pluginId
  版本:     $ver
  安装路径: $installPath

下一步：
  1. 完全退出 ZCode 后重新打开（插件与 MCP 服务在启动时加载）
  2. Settings -> Plugin Management 里应能看到已启用的 ZCode Mail
  3. 新会话里输入 /mail-check 验证

凭据（应用专用密码 / OAuth 令牌）不随仓库分发，首次使用按 README 配置到插件数据目录。
卸载：.\install.ps1 -Uninstall

"@ -ForegroundColor Gray
