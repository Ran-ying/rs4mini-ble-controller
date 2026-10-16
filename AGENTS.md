# AI developer handoff — rs4mini-ble-controller

Read this file first, then `README.md`, `node/API.md`, `docs/PROTOCOL.md`, and
`docs/DEVELOPMENT.md`. This document is intended to make development possible
without access to the original chat. Update these documents when behavior or
verification status changes.

## Objective and user decisions

- Provide an unofficial, direct BLE controller for **DJI RS 4 Mini**, initially on macOS.
- **Node.js is the authoritative implementation**; current package version is `0.7.4`.
- The user subsequently requested completion of all existing ports. Python is now
  `0.7.4`, Web shares the JS core, and the native panel is `0.3.4`. Describe the
  documented feature differences; do not claim identical APIs or hardware proof.
- After that delivery, the user requested the remaining **non-camera** capabilities
  under the same autonomous/offline conditions. Expansion work is in progress;
  see `docs/EXPANSION_PLAN.md`. The 0.7.0 source checkpoint and its remaining
  verification gates are recorded in `docs/PROJECT_STATUS.md`.
- The user requires a clear boundary between the BLE device SDK and motion/tasks
  composed above it. The modules are separated in 0.7.1; applications use only
  `RS4Mini` (native `RSGimbal`), including basic device operations. The facade
  inherits the device SDK and shares its single connection/queue/operation owner.
  See `docs/ARCHITECTURE.md`; do not count `moveTo()` as a native BLE command.
- The user requires full device-command decoding/encapsulation before further
  advanced feature development. This gate is NOT met. Keep existing advanced
  features working but add none while `protocol/COMMANDS.json` reports incomplete.
  Audit codecs, response semantics and RS 4 Mini hardware evidence separately;
  raw replies and other-model codecs are not complete target-device support.
  See `docs/SDK_COMMANDS.md`; no blind probing or hardware use while the user is away.
- The user chose direct computer control without a Bluetooth gamepad or Android intermediary.
- Nikon Z6III integration, camera autofocus/shutter/video control, and vision
  tracking were explicitly removed from the current scope. Do not restart that
  work unless the user requests it. The camera can be treated as payload.
- The name `rs4mini-ble-controller` is the repository name; `rs4mini-sdk` remains
  the existing npm/Python package name. Renaming the repository does not imply a
  package rename, npm publication, or DJI affiliation.
- User communication and primary usage docs are in Chinese. Code names are English.

## Repository map

| Path | Role |
|---|---|
| `node/src/index.js` | Node entry with independent lazy Noble backend |
| `node/src/device.js` | BLE device lifecycle, queue, streaming, feedback and shared operation coordinator |
| `node/src/controller.js` | Application entry above device SDK: existing composed motion and math |
| `node/src/noble-adapter.js` | Native Noble adapter factory and lazy cleanup |
| `node/src/protocol.js` | Pure DUML encoder and CRCs |
| `node/src/telemetry.js` | BLE stream reassembly, CRC verification, `04:05` feedback decoder |
| `node/src/*.d.ts` | TypeScript declarations; keep synchronized with runtime |
| `node/examples/` | Offline tests and separate explicit hardware demos |
| `python/` | Bleak async controller, feedback/position API, aliases and regression tests |
| `macos/` | Objective-C/AppKit/CoreBluetooth control panel and build script |
| `web/` | Web Bluetooth adapter, shared core, feedback/position page and fake GATT tests |
| `tools/ble-probe/` | macOS diagnostic probe used during original protocol research |
| `docs/` | Protocol, development findings, verification history |

Do not edit generated `.app` bundles, native binaries, `node_modules`, or caches.

## Essential protocol facts

- GATT service `FFF0`; notify `FFF4`; write-without-response `FFF5`.
- DUML starts with `55`; APP sender `02`; gimbal receiver `04`.
- Velocity command `04:01`: payload `<tilt:int16, roll:int16, pan:int16,
  zero:int16, source:uint8>` little-endian; source `02`.
- RC midpoint `1024`; normalized `-1..+1` maps to `1024 ± 660`.
- Stream commands at the configured rate, default **15 Hz**; split outgoing
  frames into **20-byte GATT chunks**. This rate is not a motor speed.
- Stop sends three all-neutral velocity frames. Recenter is `04:4C`, payload
  `FE 01`, flags `40`, and affects all axes.
- At sequence `0100`, stop golden vector is
  `551604fc020400010004010004000400040000027705`.
- `04:05` arrives at approximately **1 Hz** on the tested device. Attitude
  pitch/roll/yaw: payload `+0/+2/+4`, signed int16 LE divided by 10.
- Joint yaw: `+16 /100`; joint pitch: `+20 /10`; joint roll: `+22 /10`.
- Four float32 LE values at `+24/+28/+32/+36` have approximately unit norm.
  Quaternion component order and coordinate convention are **unverified**.
- Do not equate attitude with joint angles. Do not change the joint mapping
  based solely on a third-party decoder for a different DJI product.

## API and motion semantics

- `setVelocity({pan,tilt,roll})`: normalized values; omitted axes become zero.
  Positive Pan is right, positive Tilt is up in the original test posture.
- `setVelocityDeg()` is an empirical conversion using full scales
  Pan `37.5`, Tilt `27.5`, Roll `30` degrees/sec. These are not hardware maxima
  or guaranteed physical rates. Device joystick settings affect motion.
- `getAttitude()` and `getJointAngles()` use cached feedback by default, or wait
  when none exists. `{fresh:true, timeoutMs:3000}` waits for the next frame;
  it does not issue an active query. Returned getters copy angle/raw objects.
- `moveTo({pan,tilt,roll,...})` targets **mechanical joint angles in degrees**:
  Pan↔joint yaw, Tilt↔joint pitch, Roll↔joint roll. Targets are limited by the
  API to `-180..180`; that is not a statement of collision-free mechanical range.
- Position control uses a proportional loop over verified velocity commands,
  **not** DUML `04:0A/04:14`. Joint error to virtual-stick sign is Pan `+`,
  Tilt `-`, Roll `+`. Pan uses the shortest wrapped angular difference.
- Defaults: tolerance `1°`, total timeout `30000 ms`, telemetry timeout `3000 ms`,
  gain `0.02`, minSpeed `0.05`, maxSpeed `0.18`.
- `stop()` cancels active position/duration work, sends neutral frames, and waits
  until operation cleanup releases ownership. Handle the movement promise rejection.
- All finite operations, initial velocity writes and final stops own the motion
  slot. Conflicting commands fail with `RS4MINI_BUSY`; streaming manual velocity
  may be updated after the preceding setter settles. New bounded operations stop
  prior continuous velocity before waiting for feedback.
- Each axis inside tolerance is individually zeroed; total position timeout is
  consistently `RS4MINI_MOVE_TIMEOUT`, distinct from a shorter telemetry wait.
- Each GATT write and cleanup is bounded by `ioTimeoutMs` (default 3000 ms).
  A started DUML frame finishes its chunks before a stop; on write failure the
  session is invalidated and disconnected instead of continuing a partial frame.
- Each new process must call `connect()`. A CoreBluetooth handle cannot be shared
  across processes. Cache only the UUID; direct connect falls back to scanning.
- `disconnect()` permits reuse of the instance; `close()` closes Noble's run
  loop and permanently closes the instance. CLI `finally` blocks use `close()`.

## Development and verification

Node (no gimbal required):

```sh
cd node
npm ci
npm test
npm pack --dry-run
```

Python, after installing its dependencies in a venv:

```sh
cd python
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
```

Unified offline checks: `sh tools/check-offline.sh` (TypeScript must be cached).
Web: `npm --prefix web test`. Native: `sh macos/test.sh`.
Native macOS panel: `sh macos/build.sh`. Probe: `sh tools/ble-probe/build.sh`.
Builds need Xcode Command Line Tools; generated apps/binaries are ignored.

Explicit hardware tests, from `node/`:

```sh
npm run test:neutral
npm run example:position
RS4MINI_POSITION_DELTA=20 npm run example:position
RS4MINI_POSITION_AXIS=tilt RS4MINI_POSITION_DELTA=12 npm run example:position
RS4MINI_POSITION_AXIS=roll RS4MINI_POSITION_DELTA=12 npm run example:position
npm run example:full
```

Never run motion demos as part of default offline tests or CI. Before a new
hardware session, establish that the gimbal is powered, balanced, unobstructed,
and in scope for motion testing. Inform the user of axis and amplitude. Use
bounded actions, low initial speeds, and a `finally` cleanup. Preserve existing
session authorization; do not repeatedly request confirmation for already
authorized tests. If hardware is unavailable, finish offline work and report
that hardware verification was not performed.

Historical hardware results (development session September 2026): Pan 20°,
Tilt 12°, and Roll 12° each returned to their starting neighborhood within
the `1°` arrival tolerance. These are single-axis results, not a guarantee of
accuracy after settling, at other loads, or in simultaneous three-axis motion.
See `docs/VALIDATION.md` for exact readings. The v0.5.0 concurrency changes were
covered by fake-adapter tests; do not call them independently hardware verified.

## Completed follow-ups and remaining hardware boundaries

The former 0.5.0 software follow-ups are implemented in 0.6.0: deterministic
failure/cancellation coverage, per-axis tolerance, normalized move deadlines,
cleanup ownership, connection-stage deadlines, callback isolation, cancellable
duration operations, listener cleanup, JS-compatible Python/native half steps,
and expanded TypeScript consumer checks. See the actual tests and validation log;
passing mocks does not prove OS BLE callbacks or physical motor behavior.

Node and Python expose copied state and isolate sync/async observer failures.
Default Node controllers own independent lazy Noble backends. Power waits own
cancellable listeners, so a cancelled powered-off connection leaves no SDK timer.
Web uses the same controller via a Noble-compatible GATT adapter. Native has a
separate tested position loop and backpressure queue with fixed low-speed settings.

The user is away: do not scan, connect or move hardware until they return and
request testing. Record required real-device checks in `docs/HARDWARE_CHECKLIST.md`.
Native stops remain best-effort BLE writes. The development tree adds opt-in
bounded automatic reconnect, velocity keyframe trajectories, waypoint sequences,
saved-home axis selection and explicit-order quaternion math to Node/Python and
the shared Web SDK and native panel. Web and native have explicit controls for
home, JSON trajectories/waypoints, research profiles and quaternion math. Native
queries own the operation slot and use 30-second per-attempt reconnect deadlines;
the JS/Python limited queries may coexist with motion. No hardware or visual
verification has been performed for the new features.

`gimbal.experimental` requires explicit `rs3` or `rs3mini` research profiles.
Absolute angles and native rates use RS 3 Pan/Roll/Tilt payload order (different
from Osmo examples); sleep bytes differ by model. Limited queries correlate
session, sequence, endpoints, command and response bit. Passive extra status is
profile-labeled and never replaces verified RS 4 Mini joint feedback. No new
protocol commands have been sent to hardware. Physical completion, firmware
stop behavior, real single-axis recenter, quaternion convention and mechanical
accuracy remain unproven. Saved-home return is not firmware single-axis recenter.
Camera/vision work remains outside scope. On 2026-10-15 the user explicitly
authorized committing and pushing the source and durable handoff to GitHub.
This does not authorize npm publication or a remote binary release.

Further static research inspected the pinned official Ronin 2.2.2/7096 APK in
ignored `work/research/`. `tools/research/ronin_static.py` reconstructs metadata for
6 of 8 hidden DEX segments and extracts the readable command enum. Critical
`doPack()`/response methods still contain protected NOP stubs, not original logic.
The 43 enum entries (41 unique byte-sized IDs, including two excluded camera
names and a non-wire sentinel) and selected parameter-resource facts are recorded
in `protocol/research/ronin-2.2.2-evidence.json`; they do NOT prove RS 4 Mini paths.
Parameter indexes may have multiple names even within one resource. Do not turn
the app ranges/defaults or mode enums into safe device writes. The SDK adds only
passive legacy-DUML parameter records/ACKs with raw values and explicit research
labels. No new query/write allowlist or advanced feature was added. The APK was
not installed/executed, and no device was scanned or connected.

## Publishing and repository hygiene

- Never commit `.rs4mini-device.json`, BLE identifiers/serial suffixes, raw local
  captures, credentials, dependency directories, old personal stress scripts,
  or compiled apps. Retain sanitized test vectors and aggregate results.
- This repository contains first-party source and documentation. External
  research repositories and firmware downloads are not vendored.
- Preserve the original source folder when migrating. Use repository-relative
  paths in docs and scripts. Do not reintroduce developer-specific absolute paths.
- A repository upload does not authorize npm publishing or a binary release.
- Keep Node package versions and lockfile root metadata consistent. Record
  behavior changes in `node/CHANGELOG.md` and update public API docs and types.


## Follow-up static research (runtime stays 0.7.2 / native 0.3.2)

The pinned official MSDK provided 4.18 JAR has early-return prefixes followed by
unreachable candidate bytecode tails. `tools/research/msdk_static.py` reads them
without execution or patching; `msdk_payloads.py` contains offline hypotheses only,
never imported by SDK/UI. Evidence: `protocol/research/msdk-4.18-evidence.json`.
Old YAW_CENTER=1 conflicts with target FE01 all-axis behavior. The current Ronin
same-name class uses a boolean reset field rather than the old center enum.
Never expose those old enum numbers as target single-axis/mode support. Response
business offsets may follow command-specific Ccode stripping in the packet layer;
do not equate them with raw BLE offsets. 04:32 parsing needs external request/size
context. Handle field offsets are legacy candidates with unknown target values.
No new SDK commands, query allowlist, advanced feature or device evidence resulted.
See `tools/research/MSDK_V4.md`. JAR/AAR/class files and complete disassembly remain
ignored, not source deliverables; source release versions were not bumped.


Further current-APK identity research ties display name DJI RS 4 Mini and BLE
prefix dji rs4 mini- to HG724. Its app gimbal enum value is 103, not a validated
wire offset or target query reading. The HG724-specific abstraction registers
FollowModeSensitivity, but setter/parameter loading methods remain protected
stubs. raw resources map to gimbal_param_infos (DB.json) and
ronin2_gimbal_param_infos (jy.json); the active table selector is not recovered.
See tools/research/HG724.md and protocol/research/ronin-hg724-evidence.json.
Model identity is established in readable code; wire-command branches and target
support are not. Do not turn the enum value or resource names into SDK decoding
or writes. ronin_model_trace.py is offline-only; runtime versions remain unchanged.


## Current update: actual code-item backups recovered, runtime versions unchanged

The earlier NOP-stub limitations describe metadata-only views. A new fdex/dgc2
bank in classes6/business-05 holds plain original code_item backups. The stdlib
ronin_code_restore.py matches all 19,436 backups to exact encoded-method code_off
slots, validates complete sizes/units/tries/handlers/non-overlap, and restores an
ignored analysis DEX. Never execute or distribute that view as application code.
Optional inspection recovers the HG724 FollowModeSensitivity setter, generic
parameter loader (gimbal_param_infos/res/DB.json), named index150/size1, and 04:0F
payloads 960100/960101. The current reset doPack uses mode + boolean reset, no
axis enum. See tools/research/CODE_RESTORATION.md and
protocol/research/ronin-code-restoration-evidence.json. Existing source evidence
files remain historical snapshots. A selected static command path is now known;
full command coverage, SDK encapsulation and hardware compatibility are NOT.
ronin_app_payloads.py is offline-only, not imported by SDK/UI. Do not apply legacy
signed-index parsing to index150. Keep all-complete/advanced gates false, and do
not use hardware while the user is away. Other banks/metadata remain outside
this restoration tool's scope. No APK/JNI/app code was executed.


## Current runtime: 0.7.3 / native 0.3.3 build6

The recovered HG724 sensitivity chain is SDK code under explicit ronin-2.2.2
profile, mutually exclusive with legacy experimental profiles. App entry remains
RS4Mini/RSGimbal. Read04:10 uses explicit unsigned index/size context; headerByte
remains raw. Sensitivity write04:0F allows only index150/size1/value0or1, owns
the slot, stops first and waits for correlated ACK. No arbitrary writes/replay.
Ccode.OK=0; ACK is not physical completion. Node/Python queries may coexist with
motion; native queries own the slot and stop first. See docs/APP_COMMANDS.md.
Node76, Web13, Python3.8/3.12 each55, native54+68+3, research32 checks passed;
new tests are fake only. No hardware or live UI used. ronin_command_audit.py
fixes55classes/631method hashes (including Ccode11methods), without full vendor
instructions. Other restored command fields/model paths and SDK interfaces
remain unfinished. Both gates stay false; add no advanced features. Historical
0.7.2/no SDK sending text above is superseded for this specific batch.


## Current runtime: 0.7.4 / native 0.3.4 build7

AppCommands adds get/setCustomFollowSettings and get/setMotorSettings; Python
has snake_case aliases, native RSGimbal inherits equivalent methods. Explicit
current-App profile is still required. The eight setters are inherited Ronin2
source, not proof of HG724 firmware/UI support. Named records: custom132/size1
(bits enabled1,pitch2,roll4,yaw8), motor35/size1 (disabled1,forbidSelfie16,
forbidVertical32,roll36064). No PF/PTF presets or arbitrary writes inferred.
Setters own one slot through fresh04:10 read and04:0F ACK, stop first, preserve
unspecified bits and share one monotonic deadline after preamble. Unknown motor
bits are preserved; custom value>15 remains readable but refuses write because
it exceeds source validator range. Stop/disconnect/Web blur cancel; no replay
or rollback promise. This is a device-register transaction, no advanced feature.
See docs/APP_SETTINGS.md and protocol/research/ronin-settings-evidence.json.
ronin_settings_trace.py validates pinned APK/restored SHA, named constructors,
unique records, masks and branch polarity; no vendor code executed. Source
ranges are not mechanical safety guarantees. Tests: Node83/Web13, Python3.8/3.12
each61, native58+74+3, research35; builds/types/boundaries passed. No hardware or
live UI used; full inventory and advanced gates remain false. Other commands
still need source field/model/response audit and SDK implementation.
