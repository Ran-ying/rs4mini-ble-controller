#!/bin/sh
# Build a headless SDK runner. Only --run plus opt-in initializes Bluetooth.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "${1:-}" = --help ]; then
  echo 'Build: sh tools/hardware/sdk-maintenance-macos.sh --build'
  echo 'Real device: RS4MINI_SDK_TEST=yes RS4MINI_SDK_MAINTENANCE=fine-tune|autotune|horizontal|acceleration-echo sh tools/hardware/sdk-maintenance-macos.sh --run'
  exit 0
fi
if [ "${1:-}" != --build ] && [ "${1:-}" != --run ]; then echo 'Choose --build or --run' >&2; exit 2; fi
if [ "${1:-}" = --run ] && [ "${RS4MINI_SDK_TEST:-}" != yes ]; then echo 'Explicit SDK test opt-in required' >&2; exit 2; fi
app_dir="$repo_dir/macos/.build/SDKMaintenanceTest.app"
mkdir -p "$app_dir/Contents/MacOS" "$repo_dir/macos/.module-cache"
python3 - "$app_dir/Contents/Info.plist" <<'PY'
import plistlib,sys
with open(sys.argv[1],'wb') as f:
 plistlib.dump(dict(CFBundleExecutable='SDKMaintenanceTest',CFBundleIdentifier='local.codex.rs4mini.sdkmaintenancetest',CFBundleName='RS4Mini SDK Hardware Test',CFBundlePackageType='APPL',CFBundleVersion='1',NSBluetoothAlwaysUsageDescription='Test the user-authorized RS 4 Mini device SDK without a GUI.'),f)
PY
CLANG_MODULE_CACHE_PATH="$repo_dir/macos/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
 -framework Foundation -framework CoreBluetooth -I "$repo_dir/macos" \
 "$repo_dir/macos/RSControlCore.m" "$repo_dir/macos/RSBleDevice.m" "$repo_dir/tools/hardware/sdk-maintenance-macos.m" \
 -o "$app_dir/Contents/MacOS/SDKMaintenanceTest"
codesign --force --sign - --identifier local.codex.rs4mini.sdkmaintenancetest "$app_dir"
codesign --verify --deep --strict "$app_dir"
if [ "${1:-}" = --run ]; then mkdir -p "$repo_dir/node/captures"; export RS4MINI_CAPTURE_DIR="$repo_dir/node/captures"; exec "$app_dir/Contents/MacOS/SDKMaintenanceTest"; fi
