$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
  docker compose -f rabbitmq-docker-compose.yml up -d
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String -Pattern "chatmooc-rabbitmq|rabbitmq"
} finally {
  Pop-Location
}

