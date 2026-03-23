$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
  # Load env vars (including RABBITMQ_URL/CELERY_BROKER_URL) if present.
  if (Test-Path ".\\.env") {
    Get-Content ".\\.env" | ForEach-Object {
      $line = $_.Trim()
      if (-not $line -or $line.StartsWith("#")) { return }
      if ($line -match "^(?<k>[A-Za-z_][A-Za-z0-9_]*)=(?<v>.*)$") {
        $name = $Matches["k"]
        $value = $Matches["v"].Trim()
        $commentIndex = $value.IndexOf("#")
        if ($commentIndex -ge 0) { $value = $value.Substring(0, $commentIndex).TrimEnd() }
        if (-not [string]::IsNullOrWhiteSpace($name)) {
          Set-Item -Path "Env:$name" -Value $value
        }
      }
    }
  }

  # Ensure CELERY_BROKER_URL falls back to RABBITMQ_URL (with a sensible default) before starting Celery,
  # so comment text no longer becomes the broker URL.
  if ([string]::IsNullOrWhiteSpace($env:RABBITMQ_URL)) {
    $env:RABBITMQ_URL = "amqp://guest:guest@localhost//"
  }
  if ([string]::IsNullOrWhiteSpace($env:CELERY_BROKER_URL)) {
    $env:CELERY_BROKER_URL = $env:RABBITMQ_URL
  }

  # Start Celery worker consuming only the parse queue.
  if ([string]::IsNullOrWhiteSpace($env:RESOURCE_PARSE_QUEUE)) {
    $env:RESOURCE_PARSE_QUEUE = "resource_parse_queue"
  }
  & ".\\.venv\\Scripts\\python.exe" -m celery -A app.core.celery_core:celery_app worker -l info -Q $env:RESOURCE_PARSE_QUEUE
} finally {
  Pop-Location
}