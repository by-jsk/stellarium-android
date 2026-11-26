#!/usr/bin/env bash
# Sign a pre-verified ARM64 APK with the existing Stellar Touch private key.
set -euo pipefail

if [[ $# != 3 ]]; then
  echo 'Usage: sign-apk.sh ANDROID_BUILD_TOOLS UNSIGNED_APK OUTPUT_DIRECTORY' >&2
  exit 2
fi

tools_dir=$1
input_apk=$2
output_dir=$3
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
expected_certificate=f34938b293e28c78cc0bbd1c9730aa098b0d604ecf6990bb0f04168a89a99d68

IFS=$'\t' read -r package_id version_code version_name < <(
  python3 - "$project_dir/version.json" <<'PY'
import json
import re
import sys
from pathlib import Path

version = json.loads(Path(sys.argv[1]).read_text())
if version["packageId"] != "org.byjsk.stellartouch":
    raise SystemExit("Unexpected Stellar Touch package ID")
if type(version["versionCode"]) is not int or version["versionCode"] <= 0:
    raise SystemExit("Invalid APK version code")
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version["versionName"]):
    raise SystemExit("Invalid APK version name")
print(version["packageId"], version["versionCode"], version["versionName"], sep="\t")
PY
)

umask 077
temporary_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/stellar-signing.XXXXXXXX")
trap 'rm -rf -- "$temporary_dir"' EXIT
apk_name="StellarTouch-v${version_name}.apk"
expected_manifest="package: name='$package_id' versionCode='$version_code' versionName='$version_name'"
python3 "$project_dir/tools/check-apk.py" "$input_apk" arm64-v8a
"$tools_dir/aapt" dump badging "$input_apk" > "$temporary_dir/input.badging.txt"
grep -Fq "$expected_manifest" "$temporary_dir/input.badging.txt"
grep -Fxq "native-code: 'arm64-v8a'" "$temporary_dir/input.badging.txt"

: "${STELLAR_KEYSTORE_B64:?Set the Stellar Touch release environment keystore secret}"
: "${STELLAR_SIGN_PASSWORD:?Set the Stellar Touch release environment password secret}"
printf '%s' "$STELLAR_KEYSTORE_B64" | base64 --decode > "$temporary_dir/stellar-touch.jks"
unset STELLAR_KEYSTORE_B64
"$tools_dir/zipalign" -f -P 16 4 "$input_apk" "$temporary_dir/aligned.apk"
"$tools_dir/apksigner" sign \
  --ks "$temporary_dir/stellar-touch.jks" --ks-key-alias stellar-touch \
  --ks-pass env:STELLAR_SIGN_PASSWORD --key-pass env:STELLAR_SIGN_PASSWORD \
  --v4-signing-enabled false --out "$temporary_dir/$apk_name" "$temporary_dir/aligned.apk"
unset STELLAR_SIGN_PASSWORD
rm -- "$temporary_dir/stellar-touch.jks"

"$tools_dir/apksigner" verify --verbose --print-certs "$temporary_dir/$apk_name" > "$temporary_dir/$apk_name.signer.txt"
grep -Fxq "Signer #1 certificate SHA-256 digest: $expected_certificate" "$temporary_dir/$apk_name.signer.txt"
grep -Fxq 'Number of signers: 1' "$temporary_dir/$apk_name.signer.txt"
grep -Eq '^Verified using v[23] scheme .*: true$' "$temporary_dir/$apk_name.signer.txt"
"$tools_dir/zipalign" -c -P 16 4 "$temporary_dir/$apk_name"
"$tools_dir/aapt" dump badging "$temporary_dir/$apk_name" > "$temporary_dir/$apk_name.badging.txt"
grep -Fq "$expected_manifest" "$temporary_dir/$apk_name.badging.txt"

mkdir -- "$output_dir"
mv -- "$temporary_dir/$apk_name" "$temporary_dir/$apk_name.signer.txt" \
  "$temporary_dir/$apk_name.badging.txt" "$output_dir/"
(cd "$output_dir" && sha256sum "$apk_name" > SHA256SUMS.txt)
echo "Verified $apk_name, ARM64 16-KiB alignment and the existing Stellar Touch release signer."
