#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$project_dir/.build" "$project_dir/.module-cache"
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Werror \
  -framework Foundation "$project_dir/RSControlCore.m" "$project_dir/test-core.m" -o "$project_dir/.build/test-core"
"$project_dir/.build/test-core"
CLANG_MODULE_CACHE_PATH="$project_dir/.module-cache" xcrun clang -fobjc-arc -fmodules -Wall -Wextra -Wno-unused-parameter -Werror \
  -framework Foundation -framework CoreBluetooth "$project_dir/RSControlCore.m" "$project_dir/RSGimbal.m" "$project_dir/test-gimbal.m" -o "$project_dir/.build/test-gimbal"
"$project_dir/.build/test-gimbal"
