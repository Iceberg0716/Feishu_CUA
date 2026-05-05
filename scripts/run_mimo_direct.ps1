param(
    [string]$Instruction,
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"

$proxyVars = @(
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy"
)

foreach ($name in $proxyVars) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

if (-not $ApiKey) {
    $ApiKey = $env:MIMO_API_KEY
}

if (-not $ApiKey) {
    $ApiKey = $env:CUA_API_KEY
}

if (-not $Instruction) {
    $Instruction = "open messages module"
}

if (-not $ApiKey) {
    throw "Missing MiMo API key. Pass -ApiKey or set CUA_API_KEY first."
}

$env:MIMO_API_KEY = $ApiKey
$env:CUA_MODEL = "mimo-v2.5-pro"
$env:CUA_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

Write-Host "Running MiMo direct test without proxy..."
Write-Host "Model: $env:CUA_MODEL"
Write-Host "Base URL: $env:CUA_BASE_URL"
Write-Host "Instruction: $Instruction"

D:\python\python310\python.exe main.py -i $Instruction
