param(
  [Parameter(Mandatory=$true)][string]$BackupPath,
  [Parameter(Mandatory=$true)][string]$AgeIdentityPath,
  [Parameter(Mandatory=$true)][string]$TargetDatabaseUrl
)
$ErrorActionPreference = 'Stop'
if ($TargetDatabaseUrl -notmatch '/[^?]*(restore|test|disposable)[^?]*(\?|$)') { throw 'Restore target database name must contain restore, test, or disposable.' }
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) { throw 'pg_restore is required.' }
if (-not (Get-Command age -ErrorAction SilentlyContinue)) { throw 'age is required.' }
$backup = [IO.Path]::GetFullPath($BackupPath)
$expected = (Get-Content -LiteralPath "$backup.sha256" -Raw).Split(' ')[0].Trim().ToLowerInvariant()
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash.ToLowerInvariant()
if ($expected -ne $actual) { throw 'Backup checksum verification failed.' }
$temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ("expense-restore-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
$dump = Join-Path $temporaryDirectory 'database.dump'
try {
  & age --decrypt --identity $AgeIdentityPath --output $dump $backup
  if ($LASTEXITCODE -ne 0) { throw 'age decryption failed.' }
  & pg_restore --dbname=$TargetDatabaseUrl --clean --if-exists --no-owner --exit-on-error $dump
  if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed.' }
  Write-Output 'Restore completed; run application validation before using this database.'
} finally {
  if (Test-Path $temporaryDirectory) { Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force }
}
