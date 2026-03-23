$ErrorActionPreference = "Stop"

# Load env vars (including LANGSMITH_*) into the FastAPI process so traces work.
$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
  & ".\.venv\Scripts\uvicorn.exe" app.main:app --reload --env-file ".\.env"
} finally {
  Pop-Location
}
