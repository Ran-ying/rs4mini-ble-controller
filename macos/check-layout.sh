#!/bin/sh
# Optional macOS desktop QA. Offscreen own views only; no Bluetooth manager or production app launch.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$project_dir/.build" "$project_dir/.module-cache"
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework AppKit -framework CoreBluetooth \
  "$project_dir/test-panel-layout.m" "$project_dir/RSSDKPanel.m" "$project_dir/RSSDKActions.m" \
  "$project_dir/RSGimbal.m" "$project_dir/RSBleDevice.m" "$project_dir/RSControlCore.m" "$project_dir/RSMotionCore.m" \
  -o "$project_dir/.build/test-panel-layout"
"$project_dir/.build/test-panel-layout"
