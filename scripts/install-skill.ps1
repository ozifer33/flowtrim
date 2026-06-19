param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $InstallerArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $scriptDir "flowtrim-skill-install.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Error "node is required for this convenience installer. Use docs/install.md for manual copy paths."
  exit 1
}

& node $installer @InstallerArgs
exit $LASTEXITCODE
