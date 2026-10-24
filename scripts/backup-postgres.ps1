param(
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [Parameter(Mandatory=$true)][string]$AgeRecipient
)
$ErrorActionPreference = 'Stop'
if (-not $env:DATABASE_URL) { throw 'DATABASE_URL must be set in the current shell.' }
if ([IO.Path]::GetExtension($OutputPath) -ne '.age') { throw 'OutputPath must end in .age.' }
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) { throw 'pg_dump is required.' }
if (-not (Get-Command age -ErrorAction SilentlyContinue)) { throw 'age is required for encrypted backups.' }
$target = [IO.Path]::GetFullPath($OutputPath)
$directory = Split-Path -Parent $target
if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
$temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ("expense-backup-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
$dump = Join-Path $temporaryDirectory 'database.dump'
try {
  & pg_dump --dbname=$env:DATABASE_URL --format=custom --no-owner --file=$dump
  if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }
  & age --recipient $AgeRecipient --output $target $dump
  if ($LASTEXITCODE -ne 0) { throw 'age encryption failed.' }
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
  Set-Content -LiteralPath "$target.sha256" -Value "$hash  $([IO.Path]::GetFileName($target))" -Encoding ascii
  Write-Output "Encrypted backup and checksum created at $target"
} finally {
  if (Test-Path $temporaryDirectory) { Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force }
}
