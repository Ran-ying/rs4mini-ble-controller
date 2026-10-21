#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app_dir="$project_dir/RS 4 Mini Control.app"
cache_dir="$project_dir/.module-cache"
mkdir -p "$app_dir/Contents/MacOS" "$cache_dir"

CLANG_MODULE_CACHE_PATH="$cache_dir" xcrun clang \
  -fobjc-arc -fmodules \
  -framework Foundation -framework AppKit -framework CoreBluetooth \
  "$project_dir/RSManualControls.m" "$project_dir/RSSDKActions.m" "$project_dir/RSSDKPanel.m" "$project_dir/controller.m" "$project_dir/RSBleDevice.m" "$project_dir/RSGimbal.m" "$project_dir/RSControlCore.m" "$project_dir/RSMotionCore.m" -o "$app_dir/Contents/MacOS/RS4MiniControl"

cp "$project_dir/Info.plist" "$app_dir/Contents/Info.plist"
codesign --force --sign - --identifier local.codex.rs4minicontrol "$app_dir"
codesign --verify --deep --strict "$app_dir"
