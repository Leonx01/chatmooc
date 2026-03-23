$ErrorActionPreference = "Stop"

# Click's help output includes Unicode symbols; force UTF-8 to avoid GBK encoding crashes on Windows consoles.
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
Push-Location $repoRoot
try {
  & ".\.venv\Scripts\langgraph.exe" dev --config ".\langgraph.json"
} finally {
  Pop-Location
}
