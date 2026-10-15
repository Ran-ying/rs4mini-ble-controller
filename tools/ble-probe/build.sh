#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cache_dir="$project_dir/.module-cache"
mkdir -p "$cache_dir"

CLANG_MODULE_CACHE_PATH="$cache_dir" \
  xcrun clang -fobjc-arc -fmodules \
  -framework Foundation -framework CoreBluetooth \
  "$project_dir/probe.m" -o "$project_dir/rs4mini-probe"

app_dir="$project_dir/RS4 Mini Probe.app"
mkdir -p "$app_dir/Contents/MacOS"
cp "$project_dir/rs4mini-probe" "$app_dir/Contents/MacOS/rs4mini-probe"
cp "$project_dir/Info.plist" "$app_dir/Contents/Info.plist"
codesign --force --sign - --identifier local.codex.rs4miniprobe "$app_dir"
codesign --verify --deep --strict "$app_dir"
