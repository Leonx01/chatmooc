$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
  # Ensure env vars (like RABBITMQ_URL / RESOURCE_PARSE_QUEUE) are available.
  if (Test-Path ".\\.env") {
    Get-Content ".\\.env" | ForEach-Object {
      if ($_ -match "^(?<k>[A-Za-z_][A-Za-z0-9_]*)=(?<v>.*)$") {
        $name = $Matches["k"]
        $value = $Matches["v"]
        if (-not [string]::IsNullOrWhiteSpace($name)) {
          $env:$name = $value
        }
      }
    }
  }

  Write-Host "This project now uses Celery for parsing workers. Starting Celery worker..."
  & "$PSScriptRoot\\dev-celery-worker.ps1"
} finally {
  Pop-Location
}
