# AI developer handoff — rs4mini-ble-controller

Read this file first, then `README.md`, `node/API.md`, `docs/PROTOCOL.md`, and
`docs/DEVELOPMENT.md`. This document is intended to make development possible
without access to the original chat. Update these documents when behavior or
verification status changes.

## Objective and user decisions

- Provide an unofficial, direct BLE controller for **DJI RS 4 Mini**, initially on macOS.
- **Node.js is the authoritative implementation**; current package version is `0.7.11`.
- The user subsequently requested completion of all existing ports. Python is now
  `0.7.11`, Web shares the JS core, and the native panel is `0.3.11`. Describe the
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


## Current runtime: 0.7.5 / native 0.3.5 build8

HG724 inherits HG702.startAutoTune, which overrides Ronin2's parameter path.
DataGimbalCalibrate sends04:6A payload000101/000100 with NEEDACK.NO/flags0.
AppCommands.sendAutoTuneRequest({start:bool}) sends this only under explicit
current-App profile, owns slot through pre-stop and local write, never waits for
ACK and never claims firmware completion. Native sendAutoTuneRequest:@YES/@NO
waits for queue drain. Once sent, firmware may keep running: stop() cancels host
work/sends neutrals but does not automatically send6Afalse or guarantee abort.
The false request's physical effect is unverified. Do not expose this as a
completed AutoTune task or hold-until-firmware-complete feature.
queryCalibrationStatus queries04:6E empty body with ACK. Response Ccode is
separate from business TLVs; empty ACK has null status/percent. Passive status
requires04->02,04:6E,no response flag; cached copies/onAppStatus are separate
from query replies. Native appCalibrationStatus/appStatusHandler equivalent.
Record first tag0/1; tag0 at least2 bytes (state/percent); retain unknown tails,
last complete tag0 wins; source signed size only0..127 accepted. Unknown state
and percent>100 remain raw/null. Unknown-only/malformed records do not zero the
cache. Explicit profile changes and disconnect clear it (including Python
reports arriving during disconnect stop). No program ID/correlation exists.
See docs/APP_CALIBRATION.md and protocol/research/ronin-calibration-evidence.json.
16 method hashes, state/NEEDACK enums and override were statically verified;
no vendor code executed. Node90/Web14, Python3.8/3.12 each68, native65+83+3,
research37, types/boundaries/builds passed. No hardware/live UI used. Full
command inventory and further advanced-development gates remain false.


## Current runtime: 0.7.6 / native 0.3.6 build9

AppCommands.getMotorTuning/setMotorTuning adds twelve named numerical motor
parameters: stiffness, strength, gyroFiltering, preControl, each pitch/roll/yaw.
Explicit current-App profile required; 04:31 write and 04:32 read are separate
from ordinary 04:0F/10 despite overlapping parameter indices. Names resolve
through recovered gimbal_param_infos; index0..11, typeINT08U, size1. Writes
require one named axis/parameter and integer within source ranges (5..100,
1..100,0..100,0..100 respectively), stop first, own the operation through ACK,
and never update feedback optimistically. Reads require request width context,
retain raw header byte, preserve out-of-range returned values. No arbitrary
index writes or hardware-safe range claim. See docs/APP_MOTOR_TUNING.md.
ronin_motor_trace.py verifies pinned hashes, twelve source setter/getter chains,
26 method fingerprints and both INT08U packing branches/low-byte encoding.
Node96/Web14, Python74, native69+88+3, research38 offline checks passed; installed
packages are verified in the release handoff. No hardware/live UI used; HG724
inheritance is not firmware/UI support evidence. Both completion gates false.


## Balance-test static follow-up (runtime unchanged)

ronin_balance_trace.py pins APK/restoration hashes and 14 method fingerprints.
HG724/HG702 inherit Ronin2.startGimbalBalanceTest: BALANCE_TEST name balance_test,
value64 via common DataGimbalSetUserParams/04:0F, getter04:10, index37,size1,type0.
Not direct04:40. DB.json has duplicate same-name records at ordinals36/74 with
max1/max255. readToMemory iterates List and HashMap.put by name; later successful
insertion overwrites earlier. Do not use unique_record or first-match selection.
Status bits6..7: DEFAULT0 TESTING1 FINISH2 ERROR3; roll4..5,pitch2..3,yaw0..1;
result field minus1 indexes PASS/MARGINAL/FAIL. Zero is invalid, never PASS.
See tools/research/BALANCE_TEST.md and protocol/research/ronin-balance-evidence.json.
No SDK interface/hardware support claimed yet, no new sending or advanced feature.
Research42 tests pass on Python3.8/3.12; runtime remains0.7.6/native0.3.6.


## Current runtime: 0.7.7 / native0.3.7 build10

Four ports add sendBalanceTestRequest/getBalanceTestStatus (native equivalents,
Python snake_case aliases), explicit App profile. Fixed0F payload250140 and10
request25/index37size1. No arbitrary value/axis or inferred abort. Start owns
slot through pre-stop/write/ACK only; stop/disconnect cancel pending host work,
never claim firmware abort/completion or auto-send zero/replay. ACK releases slot.
Status is not correlated to a program ID; state bits6..7 DEFAULT/TESTING/FINISH/
ERROR0..3, roll4..5,pitch2..3,yaw0..1. Axis1/2/3 PASS/MARGINAL/FAIL;0null, each
raw retained; axisFieldsValid only mapping validity, not successful testing.
Node/Python reads may coexist with motion, native reads own slot/pre-stop.
See docs/APP_BALANCE_TEST.md. Source helper now describes researchToolProvidesSdkInterface
false rather than a historical runtime encapsulation flag. Node102/Web14,
Python80 each, native72+94+3/research42, types/boundaries/builds passed. No
hardware/live UI or advanced additions; both completion gates remain false.


## Current runtime: 0.7.8 / native0.3.8 build11

Four ports expose sendAutoCalibrationRequest/getAutoCalibrationStatus plus
Python aliases/native equivalents under explicit App profile. Inherited HG724
->HG702->Ronin2->RoninBase.startGimbalAutoCalibration resolves RONIN_COMMAND
slot22 to system_calc/index36/size1/type0. Start0F payload240101 fixed1; read10
payload24. Source status enum ordinals DEFAULT0 START1 FAIL2 SUCCESS3, not limited
to write range0..1. Unknown bytes stay raw/state null. Distinct from auto-tune
6A/6E; no shared progress/cache, automatic polling or host wait-for-completion.
Start owns slot through pre-stop/ACK only. Host stop/disconnect/blur cancel
pending transaction, never invent zero abort/replay or imply firmware completion.
No program ID, physical finish/abort or horizontal-calibration identity proof;
do not claim that gap solved. See docs/APP_SYSTEM_CALIBRATION.md and protocol/
research/ronin-system-calibration-evidence.json; pinned source tool14 fingerprints.
Node108/Web14/Python86 each/native75+101+3/research45; types/boundaries/builds
passed. No hardware/live UI or advanced additions, both completion gates false.


## Multi-bank restoration (runtime stays0.7.8/native0.3.8)

ronin_code_banks.py now restores6 structurally corroborated banks,49,542 exact
code_items: segments0/2/3/4/5/6. Segment5 SHA stays4fdbd74a05df63d72a0feb1c907d9395426ec3cdb5d6aeb45e3836d856d66654. Segments1/7 have backup tables but lack reliable
metadata suffix; no code-slot restoration or full-App/protocol claim. Shared
backup_table accepts explicit pinned entry names, default remainsclasses6; all
slot/footprint/handler/non-overlap constraints remain. Restored images never run.
Optional inspect_control_modes pins bank3 SHA and fingerprints40 UI methods
referencing six follow/RC mode keys. UI shows two-bit packing clues; fields,
axis mapping,enums,model/UI support still need audit and SDK encapsulation.
Do not expose raw mode-byte writing as completed decoding. See tools/research/
CODE_BANKS.md, protocol/research/ronin-code-banks-evidence.json and ronin-control-
mode-callers.json. Research48 tests pass inPython3.8/3.12; real pinnedAPK restores
reproduce across directories. No SDK/UI sending/hardware or advanced additions.
Both completion gates remain false. Prior only-bank5 limitations are historical.


## Current runtime0.7.9/native0.3.9 build12

Four ports get/setFollowSettings and get/setRcSettings add six named parameter
mode groups: Follow speed65/acceleration71/deadZone66; RC speed67/deadZone68/
smoothing69, all common0F/10,INT08U,size1. Cross-bank SDK/UI audit18 method
fingerprints validates Pitch shift2,Roll4,Yaw6 and Custom0/Low1/Middle2/High3.
Public modes custom/low/middle/high, no raw byte/numeric/axis pan or PF presets.
Read returns all axes/raw/unknownBits. Write validates/copies named patch, fresh
reads then modifies selected two-bit fields, preserves other axes and opaque
bits0..1, owns one slot and monotonic deadline through ACK. No replay/rollback
or firmware atomicity guarantee. Native mutable strings copied too. Custom
selects existing custom values, does not write those numeric parameters.
See docs/APP_FOLLOW_MODES.md and protocol/research/ronin-follow-modes-evidence.json.
Old40-caller evidence remains a historical scan, not full semantic completion.
No model/UI/physical effect or low-bit/PF/PTF/FPV proof; no hardware/live UI or
advanced additions. Node113/Web14/Python91 each/native79+107+3/research49,
types/boundaries/builds passed; both complete gates false.


## Numeric source research (runtime stays0.7.9/native0.3.9)

ronin_numeric_params_trace.py pins APK/SDK/UI banks and42 method fingerprints.
18 ordinary numeric records: Follow speed indicesPitch3/Roll12/Yaw2; accel15/
16/14; deadZone5/13/4, allINT16U,size2, ranges1..100 exceptdeadZone0..100.
RC speed42/43/41 INT16U,size2,0..100; deadZone27/40/26 INT08U,size1,0..100;
smoothing9/39/8 INT16U,size2,0..30. Effective method inheritance, cache-key
mapping, SettingParamCmd string constructors, common0F codec and default10
model confirmed. A missing explicit getter in enum constructors is NOT32;
mPushClazz defaultsDataGimbalGetUserParams. U8/U16 mapcase4/5 tointValue and
BytesUtil.getBytes(int), low two bytes little-endian, width from metadata.
Inherited Follow Pitch/Yaw methods checkisCustomAdvancedSettingProfile; source
range is not active-preset proof. No new numeric SDK interfaces yet.
Distinct standalone UI create smoothPitch77/Roll76/Yaw78 and maxSpeed80/79/81
aretype0,size2; App puts input_source/index72/size1/value2 first, then chosen
value in one0F request. Do not substitute as ordinary RC fields or auto-select
input source/model branch. Source combination is not firmware requirement or
physical effect proof. See tools/research/NUMERIC_PARAMS.md and protocol/
research/ronin-numeric-params-evidence.json. Research53 inbothPython environments
and actual pinned-source reproduction pass. No hardware/live UI/App execution
or sending/advanced additions; both completion gates false.


## Current runtime0.7.10/native0.3.10 build13

Four ports get/setFollowTuning and get/setRcTuning implement18 ordinary numeric
fields from numeric source evidence. Default each domain reads9, filtered by
pitch/roll/yaw and named parameter. All use common0F/10, explicitwidth1/2 and
little-endian unsigned decoding; unknown65535/255 etc stayraw withwithinSourceRange
false, never clamped or legacy error-code interpreted. Single named integer write
validates/copies before pre-stop, owns through ACK and supports cancellation/
timeout without replay. No optimistic cache, mode/preset/input-source writes.
Active firmware preset is unverified (including inherited Follow Pitch/Yaw
custom advanced profile check); both reads/writes returnactivePresetVerified:false.
Create fields/input_source72 pair remain separate and unexposed. See docs/
APP_NUMERIC_TUNING.md. Native context-based0F allowlist only expands to these18
exact index/width/range records; no arbitrary parameter writes. Boundary checker
parses JS/Python/native catalog literals offline and compares all18 to pinned
source records. Node120/Web14/Python97 each/native83+113+3/research53,
types/boundaries/builds passed. No hardware/live UI/advanced additions; both
completion gates remain false. Historical numeric research no-SDK text above
is superseded only for these18 ordinary fields, not independent create profiles.


## 0.7.10 CI timing regression fix

Initial e14762a CI38954592024 failed an existing trajectory slow-write test,
not numeric SDK: macOS runner lagged before first frame so correctly emitted
only3 cleanup neutrals, while test wrongly required4 frames. Use local fake
performance clock in that test to advance only on fake writes; add independent
pre-first-frame scheduler overrun case. Exact1 motion+3 neutral versus0+3,
no replay and cleared ownership/progress are retained. Runtime unchanged,
Node120 (was119). Test clock restored in finally; no hardware used. Prior
approval log download was deferred by approval-review usage quota; normal
review retry succeeded, credentials were never printed or saved to source.


## Current runtime: 0.7.11 / native 0.3.11 build14

get/setStandaloneTuning (Python snake_case aliases) use the existing AppCommands
SDK facade. Six source-named create speed/smoothing fields are size2; callers
must explicitly pass inputSource2, and 72/size1/value2 shares ONE 0F request with
the selected numeric value. No generic batch write, implicit source selection,
source-only API, replay, rollback, or advanced tasks. Reads10 include72 first,
retain inputSourceRaw even when not2 and unsigned unknown values; no source
switch/atomic-profile guarantee. activePresetVerified/deviceVerified/physical
completion remain false. Node/Python queries retain existing concurrency;
native query owns slot and stops first. See docs/APP_STANDALONE_TUNING.md.
ronin_standalone_trace.py reuses numeric42-method audit and fingerprints six
conditional model methods from supportProfileStandalone to product Model.HG724.
App model predicate is not live target evidence or a BLE field. Fixed hashes
and all three six-record catalogs are checked. No APK code execution, hardware
or live UI. Both completeness gates remain false; no new advanced development.

0.7.11 offline checks: Node126/Web14, Python3.8/3.12 each103, native87+119+3, research54 in bothPython environments. Installed tarball126/wheel103, types/boundaries/build pass. Fixed APK static JSON reproduced byte-for-byte. No hardware/liveUI/vendor execution.
