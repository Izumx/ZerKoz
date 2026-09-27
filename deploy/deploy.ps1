# Выкатка текущего коммита на сервер с Windows (встроенные ssh/scp).
# Пример: .\deploy\deploy.ps1 -Server ubuntu@144.24.202.61 -Key $HOME\.ssh\oracle-zherkoz.key
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$Key = "",
    [string]$Dir = "/opt/zherkoz"
)
# Не Stop: docker пишет прогресс в stderr, PowerShell 5.1 принял бы это за ошибку. Проверяем коды возврата.
$ErrorActionPreference = "Continue"
$sshArgs = @("-o", "StrictHostKeyChecking=accept-new")
if ($Key) { $sshArgs += @("-i", $Key) }

$archive = Join-Path $env:TEMP "zherkoz.tar.gz"
git archive --format=tar.gz -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Write-Host ("Архив: {0:N1} МБ" -f ((Get-Item $archive).Length / 1MB))

scp @sshArgs $archive "${Server}:/tmp/zherkoz.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

# deploy/.env на сервере не трогаем — он создаётся один раз вручную
$remote = "set -e; mkdir -p $Dir; tar -xzf /tmp/zherkoz.tar.gz -C $Dir; cd $Dir; " +
    "test -f deploy/.env || { echo 'Нет deploy/.env — скопируйте deploy/.env.example и заполните'; exit 1; }; " +
    "docker compose --env-file deploy/.env up -d --build 2>&1 | grep -vE 'Pulling fs layer|Waiting|Downloading|Extracting|Verifying' ; " +
    "docker compose --env-file deploy/.env ps"
ssh @sshArgs $Server $remote 2>&1 | ForEach-Object { "$_" }
if ($LASTEXITCODE -ne 0) { throw "deploy failed (exit $LASTEXITCODE)" }
Write-Host "Готово."
