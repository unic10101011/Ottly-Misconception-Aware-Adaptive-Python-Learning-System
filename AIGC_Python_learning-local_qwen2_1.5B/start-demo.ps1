param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function New-HexSecret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

$dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else {
    @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe')
        (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\resources\bin\docker.exe')
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerExe) {
    throw '未找到 Docker。请先安装 Docker Desktop。'
}
try {
    & $dockerExe info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker 引擎不可用'
    }
} catch {
    throw 'Docker 引擎尚未就绪。请先打开 Docker Desktop 并等待引擎启动；若显示 WSL is unresponsive，请重启 WSL 或 Windows 后重试。'
}

$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    $contents = @(
        'DB_PASSWORD=' + (New-HexSecret)
        'DB_ROOT_PASSWORD=' + (New-HexSecret)
        'JWT_SECRET=' + (New-HexSecret)
        'LOCAL_LLM_URL=http://host.docker.internal:11434/api/chat'
        'OLLAMA_MODEL=qwen2.5-coder:7b-instruct-q4_K_M'
    ) -join [Environment]::NewLine
    [System.IO.File]::WriteAllText($envFile, $contents + [Environment]::NewLine, [System.Text.Encoding]::ASCII)
    Write-Host '已生成本机演示配置 .env'
}

$ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (Test-Path -LiteralPath $ollamaExe) {
    try {
        Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/version' -UseBasicParsing -TimeoutSec 2 | Out-Null
    } catch {
        Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }
} else {
    Write-Warning '未安装 Ollama，AI 聊天暂不可用。'
}
& $dockerExe compose --progress plain up --build -d
if ($LASTEXITCODE -ne 0) {
    throw '镜像下载、构建或容器启动失败。先查看上方错误；若容器已创建，再运行 docker compose logs。'
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/api/v1/health' -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    throw '后端未通过启动检查，请运行 docker compose logs backend。'
}

Write-Host '演示版已启动：http://127.0.0.1:3000'
if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:3000'
}
