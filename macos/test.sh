#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$project_dir/.build" "$project_dir/.module-cache"
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Werror \
  -framework Foundation "$project_dir/RSControlCore.m" "$project_dir/RSMotionCore.m" "$project_dir/test-core.m" -o "$project_dir/.build/test-core"
"$project_dir/.build/test-core"
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework CoreBluetooth "$project_dir/RSControlCore.m" "$project_dir/RSMotionCore.m" "$project_dir/RSBleDevice.m" "$project_dir/RSGimbal.m" "$project_dir/test-gimbal.m" -o "$project_dir/.build/test-gimbal"
"$project_dir/.build/test-gimbal"
# Prove the device SDK links without any application/motion implementation.
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework CoreBluetooth "$project_dir/RSControlCore.m" "$project_dir/RSBleDevice.m" "$project_dir/test-device.m" -o "$project_dir/.build/test-device"
"$project_dir/.build/test-device"
# GUI command adapter routes only through the public RSGimbal SDK; no AppKit or Bluetooth manager.
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework CoreBluetooth "$project_dir/RSControlCore.m" "$project_dir/RSMotionCore.m" "$project_dir/RSBleDevice.m" "$project_dir/RSGimbal.m" "$project_dir/RSSDKActions.m" "$project_dir/test-sdk-actions.m" -o "$project_dir/.build/test-sdk-actions"
"$project_dir/.build/test-sdk-actions"
# GUI keyboard ownership uses callbacks only; no window or BLE manager is created.
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework AppKit "$project_dir/RSManualControls.m" "$project_dir/test-manual-controls.m" -o "$project_dir/.build/test-manual-controls"
"$project_dir/.build/test-manual-controls"
