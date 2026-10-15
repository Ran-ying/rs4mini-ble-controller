# macOS BLE diagnostic probe

Objective-C / CoreBluetooth diagnostic utility preserved from the original
RS 4 Mini protocol experiments. It is independent of Noble and can help diagnose
host Bluetooth permissions, GATT characteristics, and raw notifications.

```sh
sh tools/ble-probe/build.sh
tools/ble-probe/rs4mini-probe --help
tools/ble-probe/rs4mini-probe --name "DJI RS4 MINI" --timeout 15
tools/ble-probe/rs4mini-probe --connect --timeout 30
```

No arguments now means **scan only**, printing to stdout. `--connect` enumerates
GATT services/characteristics. All device-specific output remains local.

Read-only notification capture:

```sh
mkdir -p node/captures
tools/ble-probe/rs4mini-probe --telemetry-capture --capture-seconds 10 --timeout 15 --output node/captures/probe.log
cd node
npm run telemetry:analyze -- captures/probe.log
```

Other diagnostic modes include `--query-position` and `--query-degree-info`,
which write protocol requests but are not intended to move motors. The original
device ignored `04:02` and acknowledged `04:1E` without increasing feedback rate.

**Motion modes** are explicit: `--axis-capture pan|tilt|roll`,
`--neutral-test`, and `--pan-test-*`. The axis-capture modes issue bounded
positive/negative velocity phases; they are not read-only. Prefer Node's
`example:position` for ordinary control testing. Do not run probe motion modes
in automated checks or while another controller is using the gimbal.

Build output includes the command-line binary and an ad-hoc-signed app with a
Bluetooth usage description. Both are generated artifacts and ignored by Git.
macOS permissions are associated with the launching host; building an app does
not automatically grant Bluetooth access to a terminal process.
