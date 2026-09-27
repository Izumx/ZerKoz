# Выкатка текущего коммита на сервер с Windows (встроенные ssh/scp).
# Пример: .\deploy\deploy.ps1 -Server ubuntu@130.61.12.34 -Key $HOME\.ssh\oracle.key
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$Key = "",
    [string]$Dir = "/opt/zherkoz"
)
$ErrorActionPreference = "Stop"
$sshArgs = @("-o", "StrictHostKeyChecking=accept-new")
if ($Key) { $sshArgs += @("-i", $Key) }

$archive = Join-Path $env:TEMP "zherkoz.tar.gz"
git archive --format=tar.gz -o $archive HEAD
Write-Host "Архив: $((Get-Item $archive).Length / 1MB) МБ"

scp @sshArgs $archive "${Server}:/tmp/zherkoz.tar.gz"
# deploy/.env на сервере не трогаем — он создаётся один раз вручную
ssh @sshArgs $Server "set -e; mkdir -p $Dir; tar -xzf /tmp/zherkoz.tar.gz -C $Dir; cd $Dir; test -f deploy/.env || { echo 'Нет deploy/.env — скопируйте deploy/.env.example и заполните'; exit 1; }; docker compose --env-file deploy/.env up -d --build; docker compose --env-file deploy/.env ps"
Write-Host "Готово."
