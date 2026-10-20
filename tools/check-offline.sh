#!/bin/sh
# Does not scan, connect, or send commands to any Bluetooth device.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
npm --prefix node test
(
  cd node
  npm exec --offline --yes --package typescript@5.9.3 -- tsc --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext examples/types-smoke.mts
  npm pack --dry-run
)
if [ -n "${RS4MINI_PYTHON:-}" ]; then
  python_bin="$RS4MINI_PYTHON"
elif [ -x "$project_dir/python/.venv/bin/python" ]; then
  python_bin="$project_dir/python/.venv/bin/python"
else
  python_bin=python3
fi
"$python_bin" tools/check-boundaries.py
"$python_bin" -m unittest discover -s tools/research -v
"$python_bin" -m unittest discover -s python/tests -v
if [ "$(uname -s)" = Darwin ]; then
  sh macos/test.sh
  sh macos/build.sh
  sh tools/ble-probe/build.sh
  tools/ble-probe/rs4mini-probe --help
fi
