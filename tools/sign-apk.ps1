param(
    [Parameter(Mandatory=$true)][string]$InputApk,
    [Parameter(Mandatory=$true)][string]$OutputApk
)
$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$jdkRoot = (Get-ChildItem -LiteralPath (Join-Path $projectRoot '.tools/jdk17') -Directory | Select-Object -First 1).FullName
$androidTools = Join-Path $projectRoot '.tools/build-tools/android-15'
$signingKey = Join-Path $projectRoot '.secrets/stellar-touch.jks'
$signingPasswordFile = Join-Path $projectRoot '.secrets/signing-password.txt'
if (-not (Test-Path -LiteralPath $signingKey)) { throw 'Stable release signing key is missing. Do not generate a replacement for an existing app.' }
$inputPath = (Resolve-Path -LiteralPath $InputApk).Path
$outputPath = [IO.Path]::GetFullPath($OutputApk)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
$alignedPath = $outputPath + '.aligned.apk'
& (Join-Path $androidTools 'zipalign.exe') -f -P 16 4 $inputPath $alignedPath
if ($LASTEXITCODE -ne 0) { throw 'APK alignment failed' }
try {
    $env:STELLAR_SIGN_PASSWORD = [IO.File]::ReadAllText($signingPasswordFile).Trim()
    & (Join-Path $jdkRoot 'bin/java.exe') -jar (Join-Path $androidTools 'lib/apksigner.jar') sign --ks $signingKey --ks-key-alias stellar-touch --ks-pass env:STELLAR_SIGN_PASSWORD --key-pass env:STELLAR_SIGN_PASSWORD --v4-signing-enabled false --out $outputPath $alignedPath
    if ($LASTEXITCODE -ne 0) { throw 'APK signing failed' }
} finally { Remove-Item Env:STELLAR_SIGN_PASSWORD -ErrorAction SilentlyContinue }
$verification = & (Join-Path $jdkRoot 'bin/java.exe') -jar (Join-Path $androidTools 'lib/apksigner.jar') verify --verbose --print-certs $outputPath
if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed' }
$verification | Set-Content -LiteralPath ($outputPath+'.signer.txt') -Encoding utf8
& (Join-Path $androidTools 'zipalign.exe') -c -P 16 4 $outputPath
if ($LASTEXITCODE -ne 0) { throw 'Final APK alignment verification failed' }
$badging = & (Join-Path $androidTools 'aapt.exe') dump badging $outputPath
if ($LASTEXITCODE -ne 0) { throw 'APK manifest could not be inspected' }
$badging | Set-Content -LiteralPath ($outputPath+'.badging.txt') -Encoding utf8
$version = Get-Content -Raw -LiteralPath (Join-Path $projectRoot 'version.json') | ConvertFrom-Json
if (-not ($badging | Select-String -SimpleMatch ("name='"+$version.packageId+"'"))) { throw 'Unexpected APK package identity' }
if (-not ($badging | Select-String -SimpleMatch ("versionCode='"+$version.versionCode+"'"))) { throw 'Unexpected APK version code' }
if (-not ($badging | Select-String -SimpleMatch ("versionName='"+$version.versionName+"'"))) { throw 'Unexpected APK version name' }
$badging | Select-Object -First 5
$verification | Where-Object { $_ -match 'Verified|SHA-256|Verifies' }
Get-FileHash -LiteralPath $outputPath -Algorithm SHA256 | Select-Object Algorithm,Hash,Path
