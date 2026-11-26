$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv/Scripts/python.exe"
$icon = Join-Path $projectRoot "assets/app.ico"
$spec = Join-Path $projectRoot "desktop_pet.spec"
$installerScript = Join-Path $projectRoot "installer.iss"
$innoCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs/Inno Setup 6/ISCC.exe"),
    "C:/Program Files (x86)/Inno Setup 6/ISCC.exe",
    "C:/Program Files/Inno Setup 6/ISCC.exe"
)
$innoCompiler = $innoCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到项目虚拟环境，请先运行：python -m venv .venv"
}

& $python (Join-Path $projectRoot "app.py") --check
if ($LASTEXITCODE -ne 0) {
    throw "源码自检失败，退出码：$LASTEXITCODE"
}
& $python (Join-Path $projectRoot "app.py") --make-icon $icon
if ($LASTEXITCODE -ne 0) {
    throw "应用图标生成失败，退出码：$LASTEXITCODE"
}
& $python -m PyInstaller --noconfirm --clean $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
}

if ($null -eq $innoCompiler) {
    Write-Warning "未找到 Inno Setup，仅生成便携版 EXE，未生成安装包。"
} else {
    & $innoCompiler /Qp $installerScript
    if ($LASTEXITCODE -ne 0) {
        throw "安装包构建失败，退出码：$LASTEXITCODE"
    }
}

Write-Host "便携版：$projectRoot/dist/粉白桌宠.exe"
if ($null -ne $innoCompiler) {
    Write-Host "安装包：$projectRoot/dist/粉白桌宠安装包.exe"
}
