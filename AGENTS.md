# AI developer handoff — rs4mini-ble-controller

Current worktree: user requested removal of subscriptions, handle/stick writes, factory reset. Five senders and subscription-key getter removed across Node/Python/native, aliases/types/UI/examples synchronized. Offline Node250/Python3.8 SDK231/research558/native1562+265+3+230/types/boundaries/signed build passed. Worktree Node/Python0.7.37, native0.3.38/build41; source delivery pending commit/CI. See docs/RETAINED_MAINTENANCE_ACCEPTANCE.md. Full auto-tune and AUTO component completion confirmed by user, manual device result confirmation required. Stop returnedComplete100 but abort semantics not proven. System60 reads remainSTART1 and user saw no response. Pitch/Roll±0.2 ACK and measured feedback changes; larger fine tune pending user answer. Balance retest finished60polls TESTING64/no axis results, user saw no effect, clean close. Pitch1degree twice still visually unclear; Roll1degree ACK/feedback−0.5→0.7→−0.4 and clean close, user confirmed visible change without abnormality. All live clients closed. Python3.12 SDK231 also passed. Do not execute removed APIs or factory reset. Raw captures ignored/local only.

Current delivery0.7.36/native0.3.37 build40: user removed two failed active queries (getHandleSettings/queryCalibrationStatus, Python aliases, native selectors/UI actions); passive calibrationStatus remains. getMotorTuning now sends one index at a time. Single returns original reply+readMode single; multi owns operation, total read deadline/cancel, returns complete non-atomic values/parameters/replies without synthetic top-level ACK/message. Node/Python single limited-query behavior preserved; native all queries still pre-stop/exclusive. Actual direct SDK tests Node24/24, Python3.8+3.12 each24/24, native25/25 pass, including full12/axis4/parameter3/single1; all clients closed/disconnected. No setting write/motion/maintenance this turn. Prior logs below are historical. Full command/advanced/physical-task gates remainfalse. Final offline Node279/Python3.8+3.12 each260/research558/native1562+317+3+260/types/boundaries/signed build pass; installed tarball279+types/wheel260 pass, origins verified; Node113/wheel40/nativeZIP3 bytes match. Confirm exact-head CI before final delivery.

Latest user scope: test SDK usability only (Node/Python/macOS), no GUI testing. See docs/SDK_ONLY_ACCEPTANCE.md and tools/hardware/README.md. The opt-in live runners instantiate device-layer BleDevice/RSBleDevice directly, with no advanced motion/UI linked; default tests/CI never run them. Read/basic send/stop/disconnect and authorized sensitivity same-value write/readback are the current acceptance scope. Direct SDK results: Node23/26, Python3.8+3.12 each23/26, native24/27; all basic read/sensitivity1->1 ACK/readback/stop/teardown passed; motor.bulk/handle/calibration.query fail identically. Only these three failure cases cause exit1; no GUI or advanced/task execution. All clients closed/disconnected. Runtime0.7.35/native0.3.36 unchanged; do not turn this into protocol-completeness or physical calibration acceptance.

## Active full hardware acceptance (2026-10-20)

User insisted on testing all existing SDK methods. Worktree targets Node/Python0.7.36, native0.3.37/build40. See docs/HARDWARE_FULL_ACCEPTANCE.md and protocol/HARDWARE_ACCEPTANCE.json before any hardware action. Explicit user authorizations: low-speed small motion while balanced/unlocked/clear and present; exact same-value ordinary/motor settings write/readback batch and sensitivity1->0->1 restore; stable-base auto-tune including stop, system calibration, AUTO component calibration and balance test; inputSource2/Pitch speed50, handle three named values0, stick enabled=true, Pitch/Roll fine-tune0 accepting state changes; OS disconnect of only DJI gimbal. User explicitly declined factory reset: do not run it. No camera, activation or unknown-command probing.

System calibration ACK0 then30reads START1; user power-cycled and confirmed settled. Balance then ACK0 and30reads TESTING64 with null axis results; user confirmed second restart/settled and Mac unlocked. AUTO component request ACK0/empty business body then168 passive04:30 samples PROCESSING->COMPLETE100 over17.13s;60s observation and clean close. All42 user-permitted App operations have now been attempted; factory reset excluded, failures remain. User requested Web removal instead of unpairing: Web runtime/tests/CI/offline entry removed, preserve old pairing and historical evidence. Python3.8.10 fixed cached UUID path actually connected/read attitude/joints/sensitivity/closed, invalidFrames0; Python3.12 full motion session already passed. Native0.3.36 actual Pitch/stiffness41 read, Pan90.47->target92.47/settled92.21->saved-home90.57 and disconnect passed. Three Node link-loss/reconnect rounds restore zero velocity; first active moveFor cancelled, displacement0.32deg; final close again reported CoreBluetooth Unknown error (not clean-close pass). Recenter not repeated because AUTO left Pan near90deg, outside small-motion sweep scope. Auto-tune stop sent at Processing30, passiveComplete100 arrived25ms later;40s observation no further progress, no independent abort flag. Final close again Unknown error with connected=false/closed=true. All control clients now closed. Unified current Node277/Python258/research558/native1562+301+3+270/types/boundaries/signed build passed after Web removal. Runtime versions unchanged (source-scope/docs change). Full protocol/advanced and full hardware acceptance remainfalse. New opt-in hardware runners never enter default tests.

Latest retest0.7.35: docs/HARDWARE_RETEST_2026-10-20.md. Node/Python defaultmacOS teardown now cancels local CoreBluetooth connection without redundant notification-disable; explicit unsubscribe retained for generic Node adapters/Python injected clients/other platforms. Actual unsubscribe failure located in both Noble/Bleak; real disconnect succeeds. Node3 independent closes and3 static reconnect rounds+finalclose pass, Python3.12 and3.8 fixed close pass. Isolated MotorEnabled/PeripheralPosPitch subscriptions10s each still no corresponding new stream. Real stop/disconnect failures still propagate. Handled10s/6E10s and motor multi-record failures reproduced by both independent backends; persistent system/balance start registers after confirmed reboot cannot prove an ongoing task. No new maintenance start/motion/settings or pairing changes this retest. Post-autotune Roll2deg retests settle +0.1/-0.1deg at original/lower test speeds, both within0.5; not default/full-load guarantee. Unified Node281/Python3.8 SDK262/research558/native1562+301+3+270/types/boundaries/signed build pass; Python3.12 SDK262 pass. Installed tarball281+types/wheel262 pass, Node113/wheel40 modules exact. Confirm CI before claiming delivery.

Current research method and next-task order: `docs/RESEARCH_ROADMAP.md`. Read it with `docs/PROJECT_STATUS.md` and `protocol/COMMANDS.json`; historical six-bank or metadata-only conclusions must not override current eight-bank evidence. Eight-bank direct-reference reviews (roadmap priorities 1–5) landed earlier; offline queue A–E tools **compute** status from PREFIX evidence (2026-10-20). A/B/C/E currently compute `statically_exhausted_needs_hardware` (not device-verified). Queue D uses substatuses: `bit_layout_established` plus call_values/camera_isolation/stop_semantics/model_entry that are needs-hardware only with recorded dynamic/session boundaries—do not claim isolation statically disproven. Program sends stay closed. See the roadmap queue and `QUEUE_*` docs (including `QUEUE_D_PROGRAM_ISOLATION.md` and `QUEUE_E_SESSION_VERSION.md`). A missing HG724-named caller is not proof that no inherited business entry exists. inventoryComplete remains false; activation writes stay closed. The user returned and explicitly authorized low-speed small hardware tests on 2026-10-20; see docs/HARDWARE_SESSION_2026-10-20.md. Keep new advanced features gated.

Read this file first, then `README.md`, `node/API.md`, `docs/PROTOCOL.md`, and
`docs/DEVELOPMENT.md`. This document is intended to make development possible
without access to the original chat. Update these documents when behavior or
verification status changes.

## Objective and user decisions

- Provide an unofficial, direct BLE controller for **DJI RS 4 Mini**, initially on macOS.
- **Node.js is the authoritative implementation**; current worktree package version is `0.7.36`.
- The user subsequently requested completion of all existing ports. Python is now
  `0.7.36`, and the native panel is `0.3.37`. Describe the
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

## Current static research coverage

All eight pinned business DEX banks now have named offline views via `tools/research/ronin_prefix_restore.py`; use its `PREFIX_BANKS` and `business-XX-prefix-code-restored.dex` for new audits. Legacy six-bank `BANKS`/files/evidence remain unchanged for historical reproduction. Do not carry older global "01/07 metadata unrecovered" conclusions forward. Source protected-container Adler32 matches all eight; source SHA1 does not, and normalized derived checksums are not original-file proof. New 01/07 direct gimbal references are scoped supplemental evidence, not automatic full protocol/model validation. See `tools/research/PREFIX_RESTORATION.md`.

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
Native: `sh macos/test.sh`.
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


## Further profile/mode research (runtime stays 0.7.11 / native0.3.11)

ronin_profiles_trace.py fixes26 SDK/UI method fingerprints and named records:
USER_PROFILE/table_choice0/size1 resource0..5 (UI M1/M2/M3 writes0/1/2),
GIMBAL_WORK_MODE/ronin_gimbal_work_mode62/size1 resource0..128 with source
Free0/Flower1/Fpv2/Center3. Neither is automatically PF/PTF/FPV or the generic
MovementSettingsProfile enum (CUSTOM1=0,CUSTOM2=1,FAST3,MEDIUM4,SLOW5,UNKNOWN255).
HG724 condition selects new setTrackModeHG711 and new UI list FPV/Custom/3D
Roll360; legacy list has PTF/PF additionally, do not reuse its positions.
New selector disabled unlessUserProfile2. No automatic source/profile activation.
getPresetID is businessoffset2/width1, rawBLE offset NOT established; do not
flipactivePresetVerified or decode it into telemetry. See tools/research/PROFILES.md
and protocol/research/ronin-profiles-evidence.json. No added runtime SDK sending,
hardware/UI/vendor execution, or advanced features; both completeness gatesfalse.

Profile research checks:58 tests in bothPython environments, pinned APK/two-bank26-method output reproduced exactly. Unified check Node126/Web14/Python103/native87+119+3/types/boundaries/build pass. Runtime/packages unchanged.


## Subscription/push source audit (runtime stays0.7.11/native0.3.11)

ronin_subscription_trace.py fixes34 methods from pinnedAPK/bank05. 04:12 source
start selects CENTER5/id7 (SendPack packing E5), noACK; actual target routing
unverified. Groups are commandByte/highestChannelIndex/LSB bitmap, not byte
length. BaseCommand explicitmId differs from ordinal; USER_PROFILE ordinal12
channel0 belongs10, pitchstiffness channel0 belongs32. Source manager refreshes
nonempty map every1second, local reference counts; temporary get removes its
reference after3000ms, NOT firmwareTTL. Local unsubscribe trims/removes groups,
refresh skips empty map; no remote-stop/lease proof, no persistentSDK API.
Request-type unencrypted04:24 source RecvPack→DataBase→getPresetID establishes
payload offset2/width1; ACK may strip Ccode and cannot share that context.
Supersedes earlier raw-offset-unknown ONLY for this source scope, not hardware.
Do not equate it with table_choice/10, activate presets or flip verified flags.
See tools/research/SUBSCRIPTIONS.md and protocol/research/ronin-subscription-evidence.json.
Offline helper builds single group body only, neverDUML/transport; noSDK/UI
imports, hardware, vendor execution or advanced features. Both gatesfalse.

Subscription research:67 tests in bothPython environments, pinned34-method output reproduced exactly. Unified Node126/Web14/Python103/native87+119+3/types/boundaries/build passed. Earlier approval-review quota failure executed nothing; normal reviewed retry succeeded, no bypass. Runtime/install packages unchanged.


## Current runtime:0.7.12 / native0.3.12 build15

AppCommands.userParameterStatus (Pythonuser_parameter_status; native
appUserParameterStatus) passively caches complete source-layout04:24 only under
explicitronin-2.2.2. sender4→2, requesttype, unencrypted, minimum74bytes; no
zero-fill/ACK/other-endpoint interpretation or automatic subscription. All17
source getters1/2byte unsignedLE preserved with rawHex/bodyHex; enum preset2
remains unknown, notM3/PF/PTF/table_choice. Device/modelLayout/activePreset/
physicalCompletion flagsfalse. Source is generic model, nottarget-confirmed.
onAppStatus is now kind-discriminated calibration|userParameters; TS consumers
must narrowkind. Independent copied/immutable cache, observer isolation, reset
on profile/disconnect, no motion/telemetry ownership change. Allports use same
existing entry/connection. See docs/APP_USER_PARAMETERS.md. user_push_trace
fixes20methods including fillBytes→arrayComb zeroextension and IntLE; allthree
catalogs match17source records. No sends/hardware/liveUI/vendor execution or
advanced additions. Both completeness gatesfalse.

0.7.12 offline: Node131/Web14, Python3.8/3.12 each108, native91+124+3, research71 in bothPython environments. Installed Node131/Python108, types/boundaries/build pass. Pinned17-getter/20-method JSON independently reproduced. No hardware/liveUI/vendor execution.


## Fine/handle/reset source audit (runtime stays0.7.12/native0.3.12)

ronin_controls_trace.py fixes42 methods in pinnedSDK/UI source. Fine04:07 body
low signed delta byte+axiscmd: ROLL0/PITCH2/YAW4, notordinals. Effective inherited
Pitch/Roll source actions accept-2..2F, float32×10 truncate; no provenYaw action,
Roll needPauseStabilization gate/physical effect still unknown. Handle36 empty
query has8 business bytes; raw first5, last3 getters bit0. Handheld-named methods
are inHG724 chain; don't assumehardware support or conflateprofilebyte3 with
UserProfile/table_choice. Set35 source8-byte layout defaultsFF all8 fields;
doPack resets onlyfirst6, last2retain objectstate. FF firmware semantics NOT
proven, no camera/phone control added. Reset13 PlatformType.HG724 branches to
010001 (PC target verified), notemptyotherpath orGimbalType103. Scope/persistence
unverified. Save11 sourceempty body; no external direct method caller inbanks
05/03, notfullAppscan or target unsupportedproof. Helpers offlinebodyonly, noDUML/
SDK/UI imports or sends. See tools/research/FINE_HANDLE_RESET.md and
protocol/research/ronin-controls-evidence.json. SDK/ACK/hardware work remains;
both completeness gatesfalse, no advanced features or hardware/vendor execution.


## Current runtime0.7.13/native0.3.13 build16: handle read only

getHandleSettings (Python get_handle_settings; native getHandleSettingsWithTimeoutMs)
queries04:36 emptybody with correlatedACK underexplicitronin-2.2.2. Eight business
bytes afterstatus required; rawfirst5 and bit0 booleanslast3 allretain rawValue,
extra body bytes remain. No profile/table_choice/04:24 aliases, no camera/phone
controls, 35write/save/reset/fine API. Result notpassivecache; device/modelLayout/
physical flagsfalse. Source inheritedHandheld methods audited, nothardwareproof.
Node/Python existing limitedqueryconcurrency; nativeowns slot/stopsfirst. No retry,
disconnect retains3neutralcleanup. See docs/APP_HANDLE_SETTINGS.md. Catalogs in
Node/Python/nativecheckedagainst8records from42-method controls evidence. Both
completegatesfalse, no hardware/liveUI/vendor execution oradvancedaddition.

0.7.13 validation: Node135/Web14, Python3.8/3.12 each112, native94+126+3, research77 in bothPython environments. Installed Node135/Python112, types/boundaries/build pass. Pinned42-method JSON independently reproduced. No hardware/liveUI/vendor execution, wholeprotocol remainsincomplete.


## Current runtime0.7.14/native0.3.14 build17: fine request

sendFineTuneRequest({axis:pitch|roll,adjustmentDegrees:-2..2,timeoutMs}) and Python
snakealias/native equivalent encode04:07 signedtenths+axis2/0. ExplicitAppprofile,
finite nonboolean input, float32 input andmultiply10, truncatezero, noYaw action.
Snapshot beforepre-stop; owned untilcorrelatedACK, cancelled preamble sendsno07,
post-writecancel/timeout neverreplays/rollsback. ResultrequestedAdjustmentDegrees/
encodedTenths/nominalAdjustmentDegrees are sourceparameter metadata, NOT actual
motion/cumulative effect or totalcalibrationoffset. Allphysical/device flagsfalse;
stabilizationStateVerified=false. needPauseStabilization sourceinitialfalse,
updated byDataEye turnedOn&&!paused; notneutralstop. No automaticpause/vision
command or activeangle/cache changes. See docs/APP_FINE_TUNE.md. Controls audit
now49methods incl3pause and4callback fingerprints; callbacks parse no actual
angles/completion. Three axis catalogs checked. No hardware/liveUI/vendor code
execution oradvancedfeatures; remaining35/11/13 etc and wholeprotocol incomplete.


## 0.7.14微调请求验证（2026-10-17）

Node141/Web14、Python3.8/3.12各119、原生98核心+130假设备+3独立SDK、研究工具两个环境各77通过。统一离线检查含类型、边界与构建通过；安装后的Node包141/Python wheel119通过。固定49方法审计独立复现与证据JSON逐字节一致。覆盖Pitch/Roll的float32截断、参数快照、互斥、关联ACK、错误响应、取消和超时无重放；实际效果、累加、持久化及暂停稳定状态仍未验收。

第二Python环境暴露旧轨迹测试依赖调度时序：首次写入前超时会正确地只有3帧中位，旧测试要求4帧。现用局部可控时钟分别验证首次写入前0+3帧和写入后1+3帧，保持精确清理与所有权检查，未修改运行时轨迹逻辑。没有扫描、连接、移动设备、实时UI或执行厂商代码；全部命令与高级新增门槛仍false。


## 手柄写入调用及失败回退审计（运行时仍0.7.14/原生0.3.14）

固定源码控制审计现66方法。HG724继承的三个手柄setter均新建DataGimbalSetHandleParams对象，仅设置一个字段：ControllerMode→dualChannelMode/0，PitchOrRollInverse→tiltDirection/1，YawInverse→panDirection/2。模式通过ControllerMode.value传递枚举值（含UNKNOWN255）；反向参数是布尔0/1。不能从PitchOrRoll的名字扩展出独立Roll开关。未指定字段沿新对象默认FF编码，固件是否保留仍未证实；不以读值重写所有8字段替代源语义。

对应写入成功回调仅报告null，不解码回读。失败回调没有直接上报原Ccode，而按ControllerMode/PitchInvertedControlEnabled/YawInvertedControlEnabled键调用DJISDKCache.getValue；这不是已证实的直接BLE读取。缓存取值回调Class.cast后使用if-ne比较对象引用，非Object.equals；非空结果中相同引用可回报成功，否则RESULT_FAILED；结果对象为空时直接返回、没有完成回调，取值失败则传递错误。不能复制为“写入失败也成功”，也不能据此声称固件写入接受或持久化。

读取ControllerMode的上层回调用values()[raw]数组下标，不是find(raw)；方向回调仅raw==1为true，不是bit0（raw3不等于true）。SDK现有getHandleSettings继续保留原值，不照搬源代码对异常值的数组风险，也不重解释既有结果。新增3项审计测试覆盖单字段新对象、禁止singleton/多字段/未构造、引用比较与错误分支变更。没有新增SDK发送、厂商代码执行或硬件操作；手柄写入SDK及本机验收仍待完成，两个完整性门槛false。


## 2026-10-17 手柄调用/缓存回退静态研究

运行时0.7.14/原生0.3.14不变。66方法固定APK审计独立复现与JSON逐字节一致；研究工具Python3.8/3.12各80。统一离线检查Node141/Web14/Python119/原生98+130+3及类型/边界/构建通过。新增测试确认单字段新对象与引用比较，拒绝单例、多字段、缺构造和比较/错误分支变更。没有SDK发送扩展、硬件/liveUI/厂商代码执行；全部命令仍未完成。


## 0.7.15手柄单字段请求 / 原生0.3.15 build18

四端设备SDK的sendHandleSettingRequest（Python snake别名）显式App来源下仅接受dualChannelMode/tiltDirection/panDirection单字段及整数0/1，8字节35体未指定字节为源默认FF。新对象/独立体，不全量读改写、不新增相机字段。参数停止前验证/快照，复用连接/队列/操作所有权至关联ACK；取消/超时无重放或回滚，NACK直接失败、不缓存兜底成功、不自动回读。结果unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified及既有设备/物理标志均false。FF实际含义、模式/方向效果、持久化待本机验收。见docs/APP_HANDLE_WRITE.md；没有高级新增或硬件操作，全部命令门槛仍false。


## 0.7.15手柄单字段写入验证（2026-10-17）

统一离线检查Node147/Web14、Python3.8/3.12各125、原生103核心+135假设备+3独立SDK通过；研究工具两个环境各80，类型/边界/构建通过。Node tarball隔离安装后147、Python wheel隔离安装后125通过。新增三个命名字段精确FF默认载荷、独立体、输入快照、非法参数/排除字段、互斥、关联ACK、NACK不缓存兜底、请求前后取消/超时无重放及Web无Buffer编码覆盖。三端命名字段目录与66方法审计逐项比对。

安装包验证发现旧轨迹成功测试依赖60ms真实调度窗口，忙碌主机可能提前结束只发一帧导致误报。Node/Python成功测试改用局部可控时钟，每个完整两段帧推进20ms，精确检查0/20/40ms三帧插值与三帧停止；运行时不变，既有超时/取消测试保留。统一和安装回归修正后均通过。没有扫描、连接、移动设备、实时UI或厂商代码执行，FF真实效果、持久化等待本机验收，全部命令门槛false。


## 0.7.16恢复设置请求 / 原生0.3.16 build19

四端sendFactorySettingsResetRequest（Python snake别名）需显式App来源和sourcePlatform HG724，固定04:13/010001；不是类型枚举103或其他平台空体。停止前验证/快照，复用连接/队列/操作槽至关联ACK。取消/超时/断线不重发、不自动保存/回读/回滚，重连不重放。ACK不证明恢复范围、持久化、重启或物理完成，相关标志false，不自动清零/改写反馈或参数。恢复范围也未证明仅非相机字段。68方法审计新增成功/失败回调，未解析完成。见docs/APP_FACTORY_RESET.md。没有硬件/liveUI/厂商执行或高级新增；全部命令仍未完成。


## 0.7.16恢复设置源请求验证（2026-10-17）

统一离线Node154/Web14、Python3.8/3.12各132、原生106核心+141假设备+3独立SDK、研究工具两环境各80、类型/边界/构建通过。Node tarball隔离安装154、Python wheel隔离安装132通过，导入路径核对为安装目标。固定APK的68方法审计独立复现与JSON逐字节一致，新增13成功/失败回调只转交对象/映射Ccode而无完成解析；三端010001源分支比对通过。

新增精确帧/显式源平台/拒绝类型枚举103与原始体、输入快照、操作互斥、错命令/NACK、请求前后取消、超时无重发、断连与重新连接无重放。Web共享无Buffer编码；原生被动推送不完成待处理reset，断连拒绝并且只有一条reset。没有扫描、连接、移动设备或执行恢复设置，没有实时UI/厂商代码执行/高级新增。实际恢复范围、生效、持久化、重启和本机接受仍待验收，全命令门槛保持false。


## 保存命令六段引用扫描（运行时仍0.7.16/原生0.3.16）

新增ronin_save_trace.py固定APK与六段恢复视图哈希，扫描banks0/2/3/4/5/6的指令引用，区分外部直接invoke、内部invoke、分配、class常量、命令枚举和字符串。逐段计数之和268232方法、254468个带code的方法、3463422条指令（不声明全局去重或全部原始方法已恢复）。只发现bank05的4个方法：命令枚举$values/<clinit>以及保存类getInstance/start；没有外部直接调用者，其他五段无保存相关指令/字符串表线索。

带code的方法不等于原始方法全部恢复，可能含剩余保护桩；1/7段未恢复，反射/动态/本机固件路径未排除。不能据扫描缺失宣称不支持保存，也不能据命令类/空体/ACK开放HG724保存接口。没有新增SDK发送或高级功能、厂商执行/硬件操作。见tools/research/SAVE_CALLERS.md与protocol/research/ronin-save-callers-evidence.json，全命令门槛仍false。


## 2026-10-17保存命令六段扫描验证

研究工具Python3.8/3.12各85项通过（新增5项分类/哈希预检）；全部六段固定输入实际扫描独立复现与证据JSON一致，序列化键顺序统一后逐字节一致。统一离线Node154/Web14/Python132/原生106+141+3、类型/边界/构建通过。BANKS源码固定哈希与既有银行证据逐项核对，4个引用方法无外部直接调用者，不等于未支持或全App审计完成。运行时仍0.7.16/0.3.16，不新增SDK发送、硬件/厂商执行或高级功能，两个完整性门槛false。


## HG724新模式实际参数与调用顺序审计（运行时仍0.7.16/0.3.16）

ronin_profiles_trace.py现40方法。新列表index2在UI入口清除IsCustomFollowMode后调用GimbalAxisMode ThreeDRoll360，直接跳过setTrackModeHG711；不能直接把index2传该内部函数。SDK继承轴模式setter用FLOWER_SPECIAL_CMD/index34/size1，枚举value<<3，ThreeAxis/TwoAxis/Roll360/ThreeDRoll360→0/8/16/24。UI实际选择仅ThreeAxis与ThreeDRoll360；与index35电机roll360位64不同，不能互换。

FPV(index0)在必要时请求退出360到轴模式0，关闭index132自定义bit0，随后同一普通参数请求把Yaw/Pitch/Roll SmoothTrack Enabled分别index17/18/19、size1置1。Custom(index1)必要时同样退出360，再开启132 bit0，界面轴选择来自既有custom轴缓存，不自动覆盖三轴。源setIsCustomMode只是UI字段赋值，无BLE请求。模式选择仍受源UserProfile2的UI条件限制，不能自动激活预设。

CacheHelper设置调用没有串联确认，UI回调成功更新延时显示标志、失败日志/Toast；没有后续参数写入或固件补偿。源函数调用顺序不是线上包序/ACK串行证明，多请求不等于原子切换。没有新增模式SDK/发送/高级任务或硬件/厂商执行；真正完成切换、部分失败/取消/恢复与本机生效仍待实现/验收。详见tools/research/PROFILES.md与protocol/research/ronin-profiles-evidence.json。


## 2026-10-17 HG724新模式链验证

40方法固定APK/SDK/UI审计独立复现与证据JSON逐字节一致，研究工具Python3.8/3.12各88项（新增3项分支单位/轴枚举移位边界）。统一离线Node154/Web14/Python132/原生106+141+3、类型/边界/构建通过。原生模式参数17/18/19/34、枚举0/8/16/24、index2跳转绕过普通轴开关、自定义控件无设备副作用及回调无链式参数写入已核对。没有新增SDK发送/高级任务、操作硬件或执行厂商代码，运行时与安装包保持0.7.16/0.3.16，完整模式切换及全命令验收仍未完成。


## 0.7.17轴模式34读写 / 原生0.3.17 build20

四端getAxisMode/sendAxisModeRequest（Python snake别名）在显式App来源下封装34/size1。四个源枚举写0/8/16/24，读(raw>>3)&3，保留raw/unknownBits=raw&0xe7及headerByte，modelLayout/activePreset/device/physical标志false。HG724 UI只定位ThreeAxis及ThreeDRoll360，不宣称全部四种固件支持。源setter整字节写，不擅自RMW或保留其他位，otherBitsPreservationVerified/persistenceVerified=false。参数快照、写先停主机运动并独占至ACK，取消/超时/断线无重放/回滚，NACK不缓存兜底；不自动写132、17/18/19、35或激活预设，不是完整跟随模式。Node/Python有限读并发与原生读占槽差异保留。见docs/APP_AXIS_MODE.md；未操作硬件/执行厂商代码/新增高级任务，全命令未完成。


## 0.7.17轴模式命名读写验证（2026-10-17）

统一离线Node162/Web14、Python3.8/3.12各140、原生113核心+148假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball162/Python wheel140通过，Python导入路径确认为wheel目标。40方法源码独立复现与JSON逐字节一致；源事件FLOWER_SPECIAL_CMD读取右移3/掩码3及三端四枚举目录比对通过。

新增四种34写体、源读取未知位/原字节/headerByte、错参数/短体/NACK、显式profile/拒绝PF标签及原始值、参数快照/互斥、取消前不发/后不重放、超时/断连与重连无重放、Web无Buffer测试。原生查询沿用占槽/先停，Node/Python查询沿用有限并发。不自动组合132/17/18/19/35或预设，不承诺其他位保留。没有硬件/liveUI/厂商执行或高级新增，全命令门槛仍false。


## 0.7.18普通跟随轴开关 / 原生0.3.18 build21

四端getSmoothTrackAxes/sendSmoothTrackAxesRequest（Python snake别名）显式App来源下封装17/18/19、size1，默认读三轴/可过滤单轴，写非空命名布尔子集，一条0F按yaw/pitch/roll排序，未指定字段省略。源App直接参数数组路径已确认，本次未定位逐轴SDK setter；不将其不存在或本机支持当结论。读raw0/1→enabled false/true，其他→null，保留raw/header、sourceEnabled=(raw==1)与withinSourceRange，不按bit0或错误码丢值。参数快照/写先停/独占至ACK，取消/超时/断线无重放/回滚，重连不恢复请求；不自动写132/34/35/预设/输入源/保存，不是完整模式。atomicApplication/activePreset/modelLayout/device/physical/persistence相关标志false。见docs/APP_SMOOTH_TRACK.md；没有高级新增、硬件/厂商执行，全命令仍未完成。


## 0.7.18普通跟随轴验证（2026-10-17）

统一离线Node170/Web14、Python3.8/3.12各148、原生120核心+155假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball170/Python wheel148通过，Python导入路径为wheel目标。40方法源码独立复现逐字节一致，三轴事件读取raw==1及真假常量、三个命名索引目录逐项核对。

新增完整/子集/单轴单帧载荷、默认/过滤读取、异常3/255的原值/三态/源解释、错参数/短体/NACK、空/非布尔/未知字段拒绝、嵌套字典快照、互斥、取消/超时/断连重连无重放及Web无Buffer覆盖。未指定轴省略，同包ACK不等于原子应用，不自动写其他域或组合完整模式。没有扫描、连接、移动硬件、实时UI、厂商执行或高级新增，全部命令与实机验收仍未完成。


## 0.7.19配置0与工作模式62 / 原生0.3.19 build22

四端getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest（Python snake别名）显式App来源下独立读写0/62、size1。配置源范围0..5，源UI名仅0/1/2=M1/M2/M3，其他不推断运动预设；工作写仅精确Free/Flower/Fpv/Center四枚举，读取未知128/255保留raw并sourceMode=null、范围标志分别true/false。索引0不是空请求。与MovementSettingsProfile、推送preset、34/17-19/132等域分开，不自动组合模式或激活其他配置。写前验证/快照/停主机运动、独占至ACK，取消/超时/断线不重放/回滚/保存/读回，重连不重放，NACK不缓存兜底。modelLayout/activePreset/device/physical/persistence相关标志false，见docs/APP_PROFILE_VALUES.md。41方法源审计补充原始整数/枚举匹配与value访问器，未操作硬件、执行厂商代码或新增高级功能，全命令仍未完成。


## 0.7.19配置/工作模式验证（2026-10-17）

统一离线Node178/Web14、Python3.8/3.12各156、原生131核心+168假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball178/Python wheel156通过，导入路径核对为wheel目标。41方法源码独立复现逐字节一致；0/62元数据与四工作枚举三端目录比对，原始整数/枚举value访问器及事件匹配已核对。

新增零索引/零值黄金体、配置0..5与工作四枚举、范围内未知128/范围外255保留、错域/短体/NACK、拒绝布尔/超范围/跟随标签/任意字段、参数快照/互斥、请求前后取消、超时和断连重连无重放，Web无Buffer编码。未自动写其他域/保存/回读/组合完整模式，活动预设/持久化等标志false。没有扫描、连接、移动硬件、实时UI、厂商执行或高级新增，全命令仍未完成。


## 六段40枚举引用矩阵与0D证据纠正（运行时仍0.7.19/0.3.19）

新增ronin_command_refs.py扫描40非相机枚举（39不同命令值），找到50个含引用方法、31枚举有类外字段引用，没有识别到字面量写包候选。SetOnOrOff仅枚举定义/自身引用，ordinal5、wire13，三参构造不带Class；六段无猜测的同名类定义、无枚举外引用/已识别字面量候选，payload/HG724用途仍未知。不能把枚举名当类名、类构造参数当出站实现绑定，或把0D等同参数35电机位。GetPushParams零类外引用但历史本机反馈有效，证明负面检索不能判不支持。SetAngle/AngleControl同wire0A不同协议类候选，需分开核对。

清单纠正套用的“通用方法已恢复”表述，区分枚举级证据、实现方法、HG724调用和硬件验证。字面量分析只线性语法候选，无完整CFG/异常/别名/副作用证明；1/7、保护桩/反射/动态/固件仍缺。见tools/research/COMMAND_REFERENCES.md及protocol/research/ronin-command-references.json。没有新增SDK发送、厂商执行、硬件/liveUI或高级功能，全命令门槛false。


## 2026-10-17六段命令引用矩阵验证

最终工具实际六段扫描独立复现与证据JSON逐字节一致；研究工具Python3.8/3.12各99项（新增11项）。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。40枚举/39不同命令值、50含引用方法，31枚举有类外字段引用；0D无类外引用/已识别字面量候选/猜测同名类定义。0A两个枚举对应不同协议类候选，不合并为同一请求布局。构造器/引用/字面量候选均不当作实际发送、型号支持或全部请求体恢复。没有SDK发送扩展、硬件/liveUI/厂商执行或高级新增，运行时/安装包仍0.7.19/0.3.19，两门槛false。


## 原生角度控制静态路径（运行时仍0.7.19/0.3.19）

HG724继承链的rotate定义在基础DJIGimbalAbstraction，绝对/相对角分支均使用04:14；8字节yaw/roll/pitch signed LE、control/invalid位、float32角度乘10后截断和double时间限制0.1..25.5乘10已核对。源请求ACK但rotate调用无回调start后立即成功，不证明ACK或物理完成。justSendPauseData发送另一个stabilization START请求，接收ID通过映射，能力初始化/地址/暂停恢复未审完。

04:0A两个10字节类区分默认误差、标志和超时；AngleControl连续byte窄化不套用常见位图。六段仅DT501 UVC构造/方法两处类外直接调用，未定位HG724路径，不据此判设备不支持，UVC继续排除。48方法指纹及手写纯离线向量见tools/research/ANGLES.md与protocol/research/ronin-angles-evidence.json。没有新增SDK发送、硬件/厂商执行/liveUI或高级功能，全命令门槛仍false。


## 原生角度研究离线验证（2026-10-17）

固定六段实际扫描生成48方法指纹；新增10项编码/窄化/哈希预检，研究工具Python3.8/3.12各109通过。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。仅研究工具/证据/文档变化，不重打运行时安装包；无硬件/liveUI/厂商执行或高级新增。


## 角度能力覆盖及暂停重载（运行时仍0.7.19/0.3.19）

29方法静态上下文审计确认HG724继承的初始化角度范围Pitch -90..90/Yaw -180..180/Roll -30..30；Handheld Roll=false被Ronin2的min/max true覆盖，非机械安全范围或动态设备读数。getGimbalIdInProtocol仅index==1映射2，其余int映射0；DataBase存储receiverID不等于-1时覆盖SendPack.receiverId，包层加密条件未审全。

justSendPauseData的无回调重载发EYE/AppState=98，SINGLE类型17/ID7，源体0100；另一个回调重载发EYE/Stabilization=96，不能合并或当04:62/04:60。无回调请求不等待业务ACK，direct BLE依赖必要性、恢复与物理效果未验证。证据protocol/research/ronin-angle-context.json及tools/research/ANGLE_CONTEXT.md。未新增SDK发送、硬件/厂商执行/liveUI、相机/视觉或高级功能，全命令门槛false。


## 角度上下文验证（2026-10-17）

固定APK/SDK实际复现29方法指纹与初始化范围覆盖。新增9项声明提取/未知写失效/分支拒绝/精确索引/哈希预检，研究工具Python3.8/3.12各118通过。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。运行时安装包不变，无硬件或厂商执行；直接BLE依赖、恢复和物理完成仍待核对。


## stabilization状态/等待依赖静态审计（运行时仍0.7.19/0.3.19）

固定六段16方法/6直接调用方法：EYE GetPushStabilizationState=97绑定类，业务byte0的bit7开启、bit6=1且开启时未暂停、低6位原因，关闭源getter也返回paused=true。事件关闭/paused释放全部waitList，未按序号关联，不是角度到位/取消通知。等待3秒；needPause=false也发START；真实异常表16..38捕获InterruptedException到40，await中断后源标志可能保留成功，不复制为SDK取消成功。

HG724继承基础resetGimbal先调用此等待，后按平台选择DataSpecialControl或DataGimbalNewResetAndSetMode；平台分支未完整审计，不替换FE01。rotate只发送不等待；所选方法未建立恢复，不等于全App无恢复。见tools/research/STABILIZATION_DEPENDENCY.md与protocol/research/ronin-stabilization-evidence.json。没有SDK发送、相机/视觉/高级新增、硬件/liveUI/厂商执行，全部命令门槛false。


## stabilization依赖验证（2026-10-17）

实际六段复现16方法/6直接调用方法，补核PauseReason.find的OTHER回退及await真实异常表。新增9项检查，研究工具Python3.8/3.12各127通过；统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。最后补充find指纹后边界检查与两Python研究回归再次通过。运行时/安装包不变，无新增发送、硬件/厂商执行或高级功能。


## 回中源平台分支与直接App入口（运行时仍0.7.19/0.3.19）

27方法/8直接调用方法：基础resetGimbal仅PlatformType M200/M210/M210RTK选04:4C类，其余选SpecialControl；后者另按ProductType六种名字选择新旧实现，不能与HG724云台型号混用。SpecialControl业务体混合其他子系统、旧_reset保留mFlycMode且接收地址另有分支，不开放发送。

三处Ronin UI直接构造04:4C类，OTHER254+reset=true→FE01，所选方法不调用通用reset/stabilization辅助。连接/电机缓存条件、控件1000ms间隔已核对，实际HG724 UI挂载/完整可达性未验证；源字节匹配历史FE01不证明整套工作流、其他模式或物理完成。YawNoFollow0/FPV1/YawFollow2不映射PF/PTF/参数62或按轴回中。见tools/research/RESET_ROUTES.md与protocol/research/ronin-reset-routes.json。无SDK发送、相机飞行/高级新增、硬件/liveUI/厂商执行，全部命令门槛false。


## 回中分支与App入口验证（2026-10-17）

固定六段实际扫描27方法指纹/8类外直接调用方法，三个UI入口OTHER+reset true及连接/电机缓存检查已核对。新增9项检查，研究工具Python3.8/3.12各136通过；统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。运行时与安装包不变，现有FE01不替换，无硬件/厂商执行或高级新增，全命令门槛false。


## 0.7.20手柄状态被动候选 / 原生0.3.20 build23

显式ronin-2.2.2下四端handheldStickStatus/appHandheldStickStatus（Python snake别名）仅被动解码04:57：signed LE int16 X/Y、rawStateWord及bit0扳机/bit1控制、未知位/尾字节保留；不归一化或推断中心/轴映射。独立缓存、复制/不可变快照与onAppStatus kind=handheldStick，profile/断线清空，不发查询/订阅/58，不影响反馈/所有权或完成待处理请求，型号/设备/轴映射/物理标志false。23方法/2直接调用审计只见MobileHandheldController，58布尔体与ACK仅离线核对，方法名不能用来推定麦克风功能或HG724支持。无硬件/liveUI/厂商执行或高级新增，全命令未完成。见docs/APP_HANDHELD_STICK.md与tools/research/HANDHELD_STICK.md。


## 0.7.20手柄被动候选验证（2026-10-17）

固定六段实际复现23方法/2类外直接调用方法。研究工具Python3.8/3.12各144项（新增8）；统一离线Node184/Web15/Python3.8与3.12各162、原生135核心+170假设备+3独立SDK、类型/边界/构建通过。安装后的Node tarball184及类型消费、wheel162回归通过，Python导入路径核对为隔离wheel目标。

新增signed端点、独立状态位/未知高位/尾字节、短帧/ACK/加密/错端点拒绝、source gating、快照与观察者异常隔离、profile/断线清空、无58/订阅发送、通知不完成待处理参数请求、Web无Buffer验证。打包Node77文件、wheel29运行时模块、原生0.3.20/build23核对；未开启实机或实时UI，仍不能宣称完整协议或HG724手柄验证。


## 0.7.21异常/电量被动候选 / 原生0.3.21 build24

显式App来源下四端04:27/33独立abnormalStatus/batteryStatus（Python snake别名、原生app前缀）及kind事件。27有21直接getter+Roll/Pitch OR复合，不含Yaw，5字节完整已知布局；33保留原始0..255容量和尾字节，不夹取255、不并入0D02。复制/不可变快照、来源/断线清空，不影响反馈/其他缓存、所有权或待处理查询，无订阅/请求/自动控制/高级新增。36方法/2直接调用仅见MobileHandheld异常消费，无HG724布局或实机证据；型号/设备/物理标志false。见docs/APP_SOURCE_STATUS.md和tools/research/ABNORMAL_BATTERY.md，全命令门槛false。


## 0.7.21源状态候选验证（2026-10-17）

固定六段实际复现36方法/2类外直接调用方法，21字段目录逐项对比Node/Python/原生与源码证据一致。研究工具Python3.8/3.12各152（新增8）；统一离线Node190/Web16/Python两环境各168、原生139核心+172假设备+3独立SDK及类型/边界/构建通过。安装后Node190+类型消费、wheel168通过，Python路径核对为隔离wheel目标。

新增Yaw-only不算复合锁、gravity两位保留、sleep偏移4、battery255/未知尾字节、短帧/ACK/加密/错端点拒绝、来源/缓存复制及观察者异常隔离、断线/来源切换清空、无请求/订阅发送、通知不完成待处理查询、Web无Buffer检查。包内Node79文件、wheel30模块、原生0.3.21/build24核对，未运行实机或实时UI，不新增高级控制，全命令门槛false。


## 教程状态与步骤源审计（运行时仍0.7.21/0.3.21）

固定六段28方法，教程类无外部直接invoke；2B源体至少5字节，byte0步骤、offset1 signed32 LE状态，9个int0/1 getter对应bit0..8，未知23位/尾字节保留。枚举0..10，未知find回退STEP_FINISH，不能抹掉原值或作为设备完成。getStepStatus的(enumValue-2)&31使步骤0/1选择bit30/31，不推定业务用途。2C int-to-byte的一字节/ACK仅离线核对，无HG724入口/效果/恢复证明，不开放SDK发送。见tools/research/TUTORIAL.md与protocol/research/ronin-tutorial-evidence.json。没有运行时/高级新增、硬件/liveUI/厂商执行，全命令门槛false。


## 教程源审计验证（2026-10-17）

固定六段实际复现28方法/0外部直接调用。研究工具Python3.8/3.12各161项（新增9），覆盖未知回退与原值分离、signed/unsigned32视图、bit30/31回绕、9个正常步骤位、Java int低字节及哈希预检。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过。运行时与安装包仍0.7.21/0.3.21，不增加教程SDK或高级功能，不操作硬件或执行厂商代码，全命令仍未完成。


## HG724支持键声明与注册规则审计（运行时仍0.7.21/0.3.21）

固定SDK223个声明注解字段，手写KeyInfo规则模型200满足HG724支持谓词，193单字段候选唯一、7多匹配保留，不是200条BLE命令/实机能力。排除用精确Set.contains，包含用isAssignableFrom；重复包含首次保留、默认条目最后保留、getKey按HashMap首个匹配，无最具体优先证据。引用类全部有定义且无组实例化，未执行Java反射。

Rotate/ResetGimbal两条基础Action注解及12框架/动作方法指纹已核对。继承目录字段、HG724初始化覆盖、方法Map/虚调用完整路径与设备效果仍待审，不改SDK允许列表、参数行为或高级门槛。详见tools/research/KEY_SUPPORT.md和protocol/research/ronin-key-support-evidence.json；没有硬件/liveUI/厂商执行，全命令仍未完成。


## 支持键审计离线验证（2026-10-18）

固定APK/bank05实际复现223声明字段、12方法指纹和两条Action注解，重复提取JSON逐字节一致。新增14项规则/注解/哈希预检，研究工具Python3.8/3.12各175通过；统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，检查进程已结束且日志到达最后probe --help。运行时安装包仍0.7.21/0.3.21，不新增SDK发送/高级功能，无硬件/liveUI/厂商执行，全部命令门槛false。


## HG724初始化与两动作声明分派（运行时仍0.7.21/0.3.21）

固定bank05新增19方法指纹，父目录Connection/FirmwareVersion/SerialNumber三注解字段补入共226项，字符串键无重复；不是226条BLE命令。HG724 init经父类到HW初始化，component最近声明RoninBase，super链到Gimbal的GimbalKeys/getClass注册；Rotate/ResetGimbal精确签名最近声明均在基础Gimbal，无子类覆盖声明。performAction核对两Map/参数后prepend回调并Method.invoke，研究工具未执行反射。运行时实例/index、方法Map顺序/动态替换、完整参数/回调和实机仍未验证。见tools/research/REGISTRATION.md及protocol/research/ronin-registration-evidence.json；不新增SDK发送/高级功能，无硬件/liveUI/厂商执行，全命令门槛false。


## 初始化与动作声明审计验证（2026-10-18）

固定APK/bank05实际两次提取226注解字段/3继承字段/19方法指纹，JSON逐字节一致。新增11项精确签名、最近声明、循环/重复拒绝、字符串键碰撞和哈希预检，研究工具Python3.8/3.12各186通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，命令进程终态0。没有运行时接口/安装包升级、SDK发送或高级新增，无硬件/liveUI/厂商执行，全命令仍未完成。


## 固件动作程序通用源审计（运行时仍0.7.21/0.3.21）

固定六段七个程序/状态类及内部类，106方法指纹/60类外直接调用；后者均bank03，未建立HG724页面/设备支持。62添加参数move/stop/yaw/pitch/roll与包内move/stop/roll/pitch/yaw不同，float32乘10 Math.round后低16位，最多10点，停止1字节且不清点。25实际最多6点、info OR不清旧位；37最多5点、mode1两字节、总时长覆盖offset2首点时长，空mode0存在源越界，不擅自修正。63混合宽度含拍摄字段，不开放发送。

38独立状态mask3与6B记录mask7分开；38/64源isChanged发送ACK，6B首字节0/1均源success、长度有符号且未完整验证、单例保留其他程序字段。离线模型严格验长并保留重复/未知记录，不复制不安全读或缓存完成语义。29项向量/边界/哈希测试；见tools/research/PROGRAMS.md、protocol/research/ronin-program-evidence.json。未新增SDK发送、相机/高级功能，无硬件/liveUI/厂商执行，全命令门槛false。


## 动作程序通用源验证（2026-10-18）

固定六段两次实际提取的106方法指纹/60直接调用方法一致，最终版补核三种整数小端转换及TimeLaps枚举。新增29项独立十六进制、负半数/窄化、点数边界、时长覆盖/空体拒绝、独立/复合状态掩码差异、未知/重复记录、截断/有符号长度与哈希预检；研究工具Python3.8/3.12各215通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，没有SDK发送、相机/高级新增或硬件/liveUI/厂商执行，48条已知清单和两个完整性门槛仍未完成。


## 程序入口与产品缓存条件审计（运行时不变）

固定bank03/05的22方法/4真实AXML布局：PlatformType HG724 switch case9的isHandle返回1、getModel返回HG724，updateProduct写IsHandleDevice，UI helper读取缓存且忽略组件参数。CreateRoninNew菜单含三程序jump id，分别绑定Panorama/Track/PathDelay真实根类；实际主页面挂载/缓存仍待验证。附近HG724帮助分支是快门线帮助，不当程序证据。checkIsValuableForCreate虽有快门检查，但所选onClick不直接调用它，不虚构入口保护或宣称全局无保护。见tools/research/PROGRAM_ENTRY.md及protocol/research/ronin-program-entry-evidence.json。没有SDK发送、相机/高级新增或厂商执行/硬件/liveUI，全命令门槛false。


## 程序入口审计验证（2026-10-18）

实际两次提取22方法指纹/4布局AXML哈希及所选HG724分支，证据JSON逐字节一致。新增12项寄存器/重复/精确返回/未知父字段/跳转拒绝、XML控件和哈希预检；研究工具Python3.8/3.12各227通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，无新增发送、相机/高级功能、硬件/liveUI或厂商执行，全命令及高级门槛false。


## 主页面挂载与轨迹UI工作流（运行时不变）

29方法/2挂载布局补齐MainRoninNew→入口控件→子布局RoninCreateJumpTextView id→父类菜单路由的所选静态链。子类只记录点击再super。轨迹预览ACK回调直接post PREVIEWING/IDLE，是UI状态，不当物理完成。所选状态方法无直接getCmdId/isSuccess/序号核对，可能读取共享单例保留的track字段；3秒message4重请求状态订阅，不发运动停止，1200ms是UI解锁。录制/停止分支仍含相机操作，不移植入SDK。见tools/research/TRACK_WORKFLOW.md、protocol/research/ronin-track-workflow-evidence.json。没有SDK发送、相机/高级新增、厂商执行或硬件/liveUI，全命令门槛false。


## 挂载与轨迹工作流验证（2026-10-18）

固定输入两次实际复现29方法/2挂载布局，证据JSON逐字节一致；共享常量提取增加显式选择参数后，旧22方法/4布局证据独立复现仍逐字节一致。新增12项直接调用/字符串区分、描述符、控件子类/id、默认选择不变及哈希预检，研究工具Python3.8/3.12各239通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，没有SDK发送、相机/高级新增、厂商执行或硬件/liveUI，全部命令仍未完成。


## 程序基础接收路径审计（运行时不变）

固定六段、37方法/7基础程序策略：Gimbal基础枚举needCcode=true，ACK剥离外层1字节而请求通知不剥；6B block=false/mix=true可进入处理器与推送两路，38/64纯推送且源isChanged发ACK。DataBase保存按senderId数组引用，6B派生解析前先super，父层满足条件时可先post，不复制为SDK完成快照。CmdSet可反射加载CmdIdGimbalExtra；六段命名空间未找到定义，但1/7/动态未排除，基础映射不当作全App实际选择。见tools/research/PROGRAM_RECEIVE.md和protocol/research/ronin-program-receive-evidence.json。没有SDK发送/接收扩展、相机/高级新增、厂商执行或硬件/liveUI，全命令门槛false。


## 程序接收路径验证（2026-10-18）

固定输入两次实际复现37方法/7基础策略及六段扩展命名空间检索，最终证据JSON逐字节一致。新增23项外层返回码/业务成功分离、明示ccode上下文、空体/加密限制、双路与BLE ping例外、三种构造器、未解析类/哨兵拒绝及哈希预检，研究工具Python3.8/3.12各262通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。基础表条件不提升为实际扩展/本机流量，运行时/安装包不变，无新增SDK收发、相机/高级功能、硬件/liveUI或厂商执行，全命令门槛false。


## 0.7.22程序状态被动候选 / 原生0.3.22 build25

显式App来源下四端programStatus（Python snake别名，原生appProgramStatus）及kind=program事件：38独立mask3、64 unsigned16计数、6B业务0/1与62/37/63及未知/重复记录。完整验长，源负长度高位拒绝，原值/尾字节保留。仅请求型未加密通知，ACK分开；复制/不可变独立帧快照，不保留源单例旧字段，来源/断线清空，不完成查询或改变运动所有权。不新增任何发送、订阅、自动ACK、相机/高级任务或物理完成判断。见docs/APP_PROGRAM_STATUS.md；全部命令门槛false，实机/liveUI未运行。


## 0.7.22程序候选验证（2026-10-18）

统一离线Node197/Web17/Python3.8与3.12各175、原生155核心+176假设备+3独立SDK、研究262及类型/边界/构建通过。五组JSON契约向量跨Node/Python/原生一致，新增源掩码差异、unsigned计数、未知/重复/尾字节、源失败不透明体、坏TLV/负长度拒绝、快照/观察者隔离、来源/断线清空、无ACK/订阅写入和不完成查询、Web无Buffer验证。没有实机或实时UI。

实际安装tarball后197项及TypeScript消费者通过；wheel隔离安装后175项通过，device/controller/app_commands/app_program_status导入路径已核对。Node包82文件、wheel31运行时模块逐字节匹配源码；原生ZIP内容与签名构建逐字节匹配，0.3.22/build25，未启动应用。3.12构建环境缺setuptools时改用已有3.8/setuptools75.3.4离线构建wheel，未下载依赖。所有型号/设备/物理/程序关联标志false，全命令与高级新增门槛仍false。


## 0.7.23单次程序状态请求 / 原生0.3.23 build26

四端sendProgramStatusRequest仅显式App来源、固定RequestSinglePush/type2、track62/timelapse37/panorama63，6B关联未加密ACK；业务bodyHex不透明，不承诺新通知、不用旧缓存成功兜底、ACK不更新被动缓存。App通用源的唯一限定发送例外；未取得HG724专属路径或实机证据，不扩大到连续订阅/取消订阅或程序执行。Node/Python有限查询不占运动槽，stop/Web blur不取消该查询；Python任务取消、超时、断线清pending不重放。原生沿用独占事务及中位前导/清理，stop取消不等同固件程序停止。无相机/高级新增、硬件/liveUI/厂商执行，全部命令门槛false。见docs/APP_PROGRAM_REQUEST.md。


## 0.7.23单次程序状态请求验证（2026-10-18）

统一离线Node205/Web18/Python3.8各183、原生159核心+192假设备+3独立SDK、研究262及类型/边界/构建通过，进程终态0。Python3.12完整183项另行通过。覆盖三个固定请求体、错误profile/原始编号/订阅选项拒绝、关联ACK与通知隔离、输入快照、NACK/空ACK/加密ACK、超时/迟到/断线/取消及排队超时不迟发；原生独占/中位前导和Web blur有限查询差异保留。

实际安装Node tarball后205项及TypeScript消费者通过；wheel隔离安装后183项通过，device/controller/app_commands/app_program_request导入路径核对。所有通知新鲜度、型号布局、本机接受、程序关联及物理完成标志false。无硬件、实时UI、厂商代码执行或高级功能新增，全部命令门槛仍false。


## 0.7.24程序状态推送启停请求 / 原生0.3.24 build27

四端sendProgramStatusSubscriptionRequest（Python snake别名/原生等价）仅显式App来源、program track/timelapse/panorama、enabled严格布尔，6B固定type0开始/type1停止推送；不等于程序停止。关联ACK业务体不透明，notificationStreamVerified/remoteSubscriptionStateVerified等均false。被动通知独立，ACK不更新缓存、不承诺新状态，停止请求后仍可接收候选通知。没有自动刷新/反向请求/取消时撤销/断线恢复或程序执行。Node/Python有限查询与原生独占事务差异沿用0.7.23。全命令与高级门槛仍false，无硬件/liveUI/厂商执行。见docs/APP_PROGRAM_SUBSCRIPTION.md；历史0.7.23“仅type2”限定已由本版本明确扩展到type0/1固定状态请求，其他通用候选不因此开放发送。


## 0.7.24推送启停请求验证（2026-10-18）

统一离线Node213/Web19/Python3.8各191、原生167核心+217假设备+3独立SDK、研究262及类型/边界/构建通过，终态0；Python3.12完整191项另行通过。六个共享请求体跨Node/Python/原生核对，覆盖严格布尔/名称/来源/超时验证、输入复制、并发序号、ACK/通知隔离、NACK/空ACK/加密ACK、取消/超时/迟到/断线/排队不迟发和无隐式相反请求。Web保留有限查询blur差异并通过无Buffer检查。固定源程序和轨迹工作流重新实际提取，与提交的106方法/60调用及29方法/2布局证据一致。

tarball隔离安装后213项及TypeScript消费者通过；wheel隔离安装后191项通过，device/controller/app_commands/app_program_request真实导入路径核对。未扫描/连接/移动设备、运行实时UI或执行厂商代码；本机/通知流/远端订阅状态/物理效果仍未验收，全部命令和高级门槛false。


## 轨迹路点、时间与ActualPose审计（运行时仍0.7.24/0.3.24）

固定bank03/05新增51方法指纹，UI move进度1..159先float32转int，<=60为秒、>60为(progress-59)*60，停留0..60秒；默认2秒，反向转换有损，JSON move仅上限6000且stop直接float，不当固件安全范围。track preview取保存首点时间，sendToDeviceStart清空首轮后最终首点move=0，两者Roll固定0；onPointAdd忽略回调Roll，JSON保留值也不改变源发送0规则。

04:66 ActualPose P/R/Y mId34/35/36与MotorAngle16/17/18分开；选定Ronin2缓存生产端getP/Y/RActualPose→PeripheralPosPitch/Yaw/Roll，经路径控件转成路点。不能改写或等同现有04:05关节/姿态映射。源按长度1signed byte/2short LE/4int LE/8long后窄化int，转float32再除10；旧map可保留其他记录/缺失补0，离线视图不复制该语义，未知/重复/其他宽度保留。源flag1记录分支、signed长度与完整验长区分。preview所选直接调用无相机，但完整间接/固件隔离仍false；参考系、型号、执行/停止未验收。

见tools/research/TRACK_POINTS.md、ronin_track_points.py与protocol/research/ronin-track-points-evidence.json。未新增SDK解码/发送、订阅或高级功能，无硬件/liveUI/厂商执行，全命令门槛false。


## 轨迹路点与ActualPose研究验证（2026-10-18）

最终固定APK/bank03/05实际两次复现51方法指纹、时间/参数路径和六项源DataType，证据JSON逐字节一致。新增22项边界测试；研究工具Python3.8与3.12各284通过。覆盖float32进度与分段/反向损失、pose/motor区分、signed宽度/long窄化/浮点舍入、未知/重复/缺失/截断、局部寄存器来源和两段哈希预检。统一离线Node213/Web19/Python191/原生167+217+3、类型/边界/构建通过，终态0且日志到达最终probe --help。Node/Python/macOS/Web所有源码目录与2eb2298相同，运行时/安装包保持0.7.24/0.3.24，无新增SDK收发/订阅/高级功能或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.25外设状态候选 / 原生0.3.25 build28

固定bank05新增70方法审计、46 DataType/43 getter视图。04:66基础表block=false/mix=false纯推送、请求业务偏移0；动态Extra/本机未证明。SDK仅显式App来源sender4→2未加密请求通知，新增peripheralStatus（Python snake别名、原生appPeripheralStatus）与kind=peripheral，独立帧快照、完整验长、未知/重复保留、复制/不可变、来源/断线清空，不完成查询/改变运动/自动ACK订阅或更新04:05。

YGyroOut/PAcceOut共mId21，分别除10/100，保留双sourceViews/ambiguous，禁止猜成22；GPS先整数除1000000再double，不修正。三void方法不造电流字段，Other255与负signed键分开。len1/2 signed，其余尾补0/低32位（含8字节窄化），实际空记录源0与缺失不补0分开，float32顺序保留。来源名不等于本机传感器/单位/参考系。所有本机/型号/参考系/物理完成标志false，无新增发送/高级/相机或硬件/liveUI/厂商执行，全命令门槛false。见docs/APP_PERIPHERAL_STATUS.md、tools/research/PERIPHERAL.md和protocol/research/ronin-peripheral-evidence.json。


## 0.7.25外设候选验证（2026-10-18）

固定源70方法/46类型/43视图两次实际提取，证据JSON逐字节一致。研究工具Python3.8与3.12各293项通过（新增9），六组共享契约覆盖完整目录、tag21碰撞、GPS整数截断、实际空记录/缺失、未知/重复/void及全长度0..127补零/符号/窄化。三端目录均逐项匹配源证据。

统一离线Node220/Web20/Python3.8共198、原生309核心+224假设备+3独立SDK、类型/边界/构建通过，终态0；Python3.12完整198另行通过。新增缓存复制/不可变/观察者隔离、来源/断线清空、CRC重组下的通知/查询/运动槽隔离、无ACK/订阅/控制写入及Web无Buffer验证。

实际安装Node tarball后220项及TypeScript消费者通过；wheel隔离安装后198项通过，device/controller/app_commands/app_peripheral导入路径核对。全部型号/设备/参考系/物理标志false，未扫描/连接/移动设备、运行实时UI或执行厂商代码；没有新增发送/高级功能，全部命令门槛false。


## 完整订阅目录与初始化条件（运行时仍0.7.25/0.3.25）

新增只读ronin_subscription_catalog.py固定APK/bank05/DB资源，24方法、81 BaseCommand、152不同注册键（98/12/42归10/32/66），DB-present解析成121命令频道对/17别名组；不是152设备能力。89键显式Base、42直接、21资源条件（15 Base）缺元数据时mId保留Java默认0，不静默选DB索引或0作为固定SDK表。

FollowModeSensitivity和GimbalControlState分别受isSupportStateSince4Gen控制；11旧组件/None等false，默认true，HG724声明走默认；不是型号白名单或本机缓存证明。保留独立if区间，离线snapshot选择资源键须明确DB-present/missing、条件键须显式true，仅稳定分析分支。空选择拒绝，不当远端停止；重复/别名去重位图，66/21歧义保留。CENTER/id7 E5无ACK、刷新/本地移除不证明租期/远端替换或停止。

源/模型/注册构造/资源初始化/本机均未执行或证明；不新增SDK收发/订阅对象/高级功能，无硬件/liveUI/厂商执行，全命令门槛false。见tools/research/SUBSCRIPTION_CATALOG.md及protocol/research/ronin-subscription-catalog.json。


## 完整订阅目录验证（2026-10-18）

固定APK/bank05/DB实际两次提取24方法指纹与152命名注册，最终JSON逐字节一致；81 BaseCommand、121个DB-present命令频道对、17组别名、21资源条件键/15 Base及两处型号条件已核对。新增19项边界，研究工具Python3.8与3.12各312通过。覆盖索引非ordinal、缺失0分支/显式条件、全目录与别名位图、三命令空间、寄存器覆盖/重复/未知注册、switch数组字段和哈希预检。

统一离线Node220/Web20/Python198/原生309+224+3及类型/边界/构建通过，终态0且日志到达最后probe --help。Node/Python/macOS/Web目录与998019a相同，运行时及安装包保持0.7.25/0.3.25，不新增SDK发送/订阅管理或高级功能。资源加载顺序、组件缓存、本机路由/租期/远端停止未验收；没有硬件/liveUI/厂商代码执行，全命令门槛false。


## 订阅初始化审计（2026-10-18）

固定六段13方法审计确认元数据异步加载、逐项发布与BaseCommand构造时一次性捕获；不能推断真实调度、竞争或捕获0。独立SDK可明确选择固定DB已加载的索引分支，无需依赖App缓存；本机路由/通知/远端取消仍未验证。见[SUBSCRIPTION_INIT.md](tools/research/SUBSCRIPTION_INIT.md)和证据protocol/research/ronin-subscription-init-evidence.json。两次实际提取JSON逐字节一致，新增7项研究测试。此研究检查点不发布新的运行时版本；已提交运行时仍0.7.25/0.3.25。单次订阅SDK正在工作树中开发，尚未交付，不计作已完成；全命令与高级门槛仍false，无硬件或厂商执行。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](docs/APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


0.7.26统一离线检查终态0：Node229/Web21/Python3.8及3.12各205、原生324核心+233生命周期+3独立SDK、研究319；类型/分层/三端目录投影及原生签名构建通过。专项覆盖发送前取消、已开始多段完整写后清理、busy、源切换阻止、写失败/超时及无重发；本机/通知/远端状态仍false。未执行硬件或实时UI。

0.7.26交付包已隔离安装：Node tarball229项及严格TypeScript消费者通过，wheel205项通过且device/controller/app_commands/app_parameter_subscription导入位于隔离安装目录。Node92文件、wheel34模块与源码逐字节一致；原生ZIP3文件与签名构建一致（0.3.26/build29），未启动应用。没有发布npm或远程二进制Release。


## 外设数据04:69源审计（运行时不变）

固定六段36方法、12数据类型/4来源枚举，核对tag2的控制来源及三轴signed16原值、无ACK start、空doPack和基础双路分发。仅定位跟踪界面读取两轴的一个直接调用者，无HG724或物理单位/路由证据。源旧字段保留/短包只清速度与离线独立帧视图区分；未增加SDK收发、相机/视觉或高级功能。见[EXTERNAL_DEVICE.md](tools/research/EXTERNAL_DEVICE.md)和protocol/research/ronin-external-device-evidence.json。运行时仍0.7.26/0.3.26，全部命令及高级门槛false，无硬件/实时UI/厂商执行。


04:69源研究验证（2026-10-18）：最终固定输入实际提取两次，36方法/1外部直接调用/0外部类型化声明证据JSON逐字节一致。11项新增研究测试通过，Python3.8/3.12研究各330项；统一离线Node229/Web21/Python205/原生324+233+3及类型/边界/构建通过。运行时/安装包仍0.7.26/0.3.26，没有新增SDK收发、相机/视觉/高级功能或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](docs/APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


0.7.27离线验收：统一Node235/Web22/Python3.8与3.12各211、原生356核心+240生命周期+3独立SDK、研究330及严格类型/边界/构建通过，终态0。七个外设契约向量跨端一致；覆盖signed16端点/顺序、Other7与未知255、重复/未知/尾部、负长度/截断整帧拒绝、复制/不可变快照、观察者异常、来源/断线清空、pending查询与运动所有权隔离、Web无Buffer。实际隔离安装tarball235项与类型、wheel211项通过；device/controller/app_commands/app_external_device导入路径核对。Node95文件、wheel35模块、原生ZIP3文件与源码/签名构建逐字节一致（0.3.27/build30），未启动应用。本机/单位/参考系与全部命令门槛仍false。


## 校准08/30域与近似类绑定研究

固定六段48方法、17直接调用、9类型化声明/9枚举引用，确认04:30实际绑定SensorCalibrateStatus而非近似AutoCalibrationStatus；30状态COMPLETE0/PROCESSING1/FAIL3/OTHER9，与08响应FAIL0/SUCCESS1/PROCESSING2分开，不复用bool inProgress或system_calc表。08单字节部件及ACK业务偏移已核对，型号入口/实际扩展、路由/物理中止仍未完成。详见[校准源审计](tools/research/SENSOR_CALIBRATION.md)及protocol/research/ronin-sensor-calibration-evidence.json。仅离线研究，运行时0.7.27/0.3.27不变，没有SDK收发、相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


校准08/30研究验证（2026-10-18）：48方法/17直接调用/9类型化声明/9外部枚举引用的最终固定输入实际提取两次，证据JSON逐字节一致。新增12项测试，Python3.8/3.12研究各342项通过；统一离线Node235/Web22/Python211/原生356+240+3及类型、边界、构建通过，终态0。没有SDK收发或运行时版本变更，既有0.7.27/0.3.27不变；无硬件/liveUI/厂商执行或相机/视觉/高级新增，全命令与高级门槛false。


## 0.7.28传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](docs/APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


0.7.28离线验收：统一Node241/Web23/Python3.8与3.12各217、原生637核心+247生命周期+3独立SDK、研究342及严格类型/边界/构建通过，终态0。七组源向量跨端一致，完整uint8/FAIL3与未知2/尾字节、坏包、快照/观察者、来源/断线、COMPLETE不结束查询/运动与Web无Buffer覆盖；修正示例事件分派对新增kind的假设。隔离安装tarball241项与类型、wheel217项通过，device/controller/app_commands/app_sensor_calibration实际安装导入位置核对；Node98文件、wheel36模块及原生ZIP3文件与源码/签名构建逐字节一致（0.3.28/build31），未启动应用。本机布局/单位/请求关联/物理完成及完整命令门槛仍false，无硬件/liveUI/厂商执行。


## 校准入口条件与HG724静态分支研究

63方法/2布局核对SystemStatus→新设置构造链、普通GYRO05/高级AUTO00的04:08及MotorEnabled缓存门槛。所选项与ModelName均HG724的显式源码情形中，普通隐藏/高级显示且旁路版本；阈值00.02.32.25严格大于、缓存/异步可见性与实际设备分开。高级ACK后60秒本地计时和百分比显示不证明固件中止/请求关联。见[校准入口研究](tools/research/CALIBRATION_ENTRY.md)及protocol/research/ronin-calibration-entry-evidence.json。不与system_calc/index36混用，未新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.28/0.3.28，完整命令门槛false。


校准入口条件验证（2026-10-18）：最终工具独立提取两次，63方法/2布局证据JSON逐字节一致。新增13研究测试，Python3.8/3.12研究各355项通过；统一离线Node241/Web23/Python217/原生637+247+3及类型/边界/构建通过，终态0。静态HG724所选项/缓存条件不提升为现场身份、实际Activity挂载或固件支持；60秒UI计时不证明中止。未新增SDK收发、相机/视觉/高级功能，运行时/安装包保持0.7.28/0.3.28，无硬件/liveUI/厂商执行，完整命令和高级门槛false。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


0.7.29接收边界离线验收（2026-10-18）：统一检查终态0，Node247/Web24/Python3.8与3.12各222、原生669核心+250假设备生命周期+3独立SDK、研究355，类型/分层/签名构建通过。覆盖全部非零加密模式、无效flags、ACK错误分类、加密读取不推进写入、缓存隔离与定位等待下的原始假反馈；没有创建蓝牙会话、运行实时UI或执行厂商代码。未实现解密/协商或开放04:08，全部命令与高级门槛仍false。


0.7.29实际安装交付验证：Node tarball隔离安装后247项与严格TypeScript消费者通过；wheel隔离安装后222项通过，app_protocol/app_calibration/telemetry/experimental_protocol实际导入位置核对。Node99文件、wheel36模块及原生ZIP3文件逐字节匹配本次源码/签名构建，原生版本0.3.29/build32，未启动应用。没有npm发布或GitHub二进制Release。


## 校准默认包头与条件加密研究

固定六段28方法审计确认04:08新对象默认APP/id0→GIMBAL/id0、条件加密前flags40；NEEDACK.YES线上值2不是ordinal。通用发送层可按可变会话策略加密包括命令集/命令号的区间；接收事件关闭仍可能运行分类分支，不把业务Encrypt.NO当最终线上保证。见[校准传输审计](tools/research/CALIBRATION_TRANSPORT.md)（仓库根目录）及protocol/research/ronin-calibration-transport-evidence.json。未实现/执行JNI或APK、未新增SDK收发/高级功能、没有硬件或实时UI，运行时仍0.7.29/0.3.29，完整命令门槛false。


校准传输研究验证（2026-10-18）：最终固定输入实际提取两次，28方法/1直接setter调用者（两次调用）证据JSON逐字节一致；新增13测试，研究Python3.8与3.12各368通过。统一离线Node247/Web24/Python222/原生669+250+3及类型/边界/构建通过，终态0。Node/Python/Web/macOS运行时源码与0875cdb一致，安装包保持0.7.29/0.3.29；未新增SDK发送、解密、相机/视觉/高级功能或硬件/liveUI/厂商代码执行，完整命令门槛false。


## BLE直连路由与默认策略研究

固定六段37方法核对BluetoothService→Main DJIPackManager→通用parseOne，以及监听、常规发送队列、服务切换、分片与GATT写入。Main继承needCheckEncrypt=true且构造enabledSetDataEvent=true，与DataBase共享加密管理器单例；源路由/构造策略已定位，实际会话与对端接受仍未验证。五处直接字段写入限构造，其他管理器false不套用到BLE。见[BLE路由研究](tools/research/BLE_ROUTE.md)（仓库根目录）及protocol/research/ronin-ble-route-evidence.json。未新增SDK收发/解密/高级功能，无硬件/liveUI/厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


BLE路由研究验证（2026-10-18）：最终固定输入实际提取两次，37方法/5个直接字段写入构造方法证据JSON逐字节一致。新增11项测试，研究Python3.8与3.12各379通过；统一离线Node247/Web24/Python222/原生669+250+3及类型/分层/构建通过，终态0。运行时目录与30b2a64完全一致，0.7.29/0.3.29安装包不变。没有SDK发送/解密/相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


## 04:08 ACK与业务域研究

固定bank05独立核对20方法，基础表ACK剥离ccode后part/status对应原始payload1/2；GIMBAL回调成功仅返回码0，与业务SUCCESS1分开。短业务体不补PROCESSING；源混合命令key仅命令集/命令/序号，不照搬到SDK严格会话/ACK/端点关联。见[校准ACK研究](tools/research/CALIBRATION_ACK.md)（仓库根目录）及protocol/research/ronin-calibration-ack-evidence.json。没有SDK发送/解密/高级新增、硬件/liveUI或厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


校准ACK研究验证（2026-10-18）：最终固定输入实际提取两次，20方法证据JSON逐字节一致。新增12项测试，研究Python3.8与3.12各391通过，覆盖全uint8部件/状态/非零返回码、短业务体、密文拒绝和key边界；统一离线Node247/Web24/Python222/原生669+250+3及类型/分层/构建通过，终态0。运行时目录与a3d4002一致，0.7.29/0.3.29安装包不变，无SDK发送/解密/高级新增或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


0.7.30离线验收：电机门槛固定输入实际提取两次、3方法/资源记录证据逐字节一致；新增4研究测试，Python3.8/3.12研究各395通过。统一Node255/Web25/Python3.8共230、原生949核心+263假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0；Python3.12完整230另行通过。七组跨端契约覆盖ACK/业务失败/未知/短体/尾部，事务覆盖禁用、坏读数、加密、busy、源切换、取消前后、迟到响应和共享预算。未操作硬件/实时UI/厂商代码，全部命令门槛仍false。


0.7.30实际安装交付验证：Node tarball隔离安装后255项与严格TypeScript消费者通过；wheel隔离安装后230项通过，app_commands/app_component_calibration/device/controller导入位置核对。Node102文件、wheel37模块、原生ZIP3文件与本次源码/签名构建逐字节一致，原生0.3.30/build33，未启动应用。没有npm发布或GitHub二进制Release。


## HG724手柄工厂与04:58键绑定研究

固定bank05核对19方法与注解，HG724条件工厂选择MobileHandheldControllerAbstraction；StickGimbalControlEnabled键支持和实际Setter注解对应04:58布尔类。方法名中的MicroPhones不定义功能，不新增麦克风/相机接口。工厂参数1是数量、普通index0，不改作接收地址；源链不证明现场反射/注册或固件效果。见[手柄绑定研究](tools/research/HANDHELD_BINDING.md)（仓库根目录）及protocol/research/ronin-handheld-binding-evidence.json。未新增SDK收发/高级功能，无硬件/liveUI/厂商执行，运行时0.7.30/0.3.30及全命令false不变。


手柄绑定研究验证（2026-10-19）：最终固定输入实际提取两次，19方法/平台switch/Key与Setter注解证据JSON逐字节一致。新增8测试，研究Python3.8与3.12各403通过；统一离线Node255/Web25/Python230/原生949+263+3及类型/分层/构建通过，终态0。运行时目录与bac83a2完全一致，0.7.30/0.3.30安装包不变。没有SDK发送、麦克风/相机/高级新增或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.31手柄摇杆开关候选 / 原生0.3.31 build34

显式App来源新增sendHandheldStickControlRequest(enabled:boolean)，停止前验证/快照，同一操作槽内中位停止后一次04:58 bool00/01并等待严格关联ACK。不透明尾部保留，requestedEnabled不回写57缓存；无订阅/查询/重试/重放/反向回滚、摇杆接管或麦克风/相机/高级新增。见 docs/APP_HANDHELD_STICK_CONTROL.md（仓库根目录）。型号源链不等于实机效果或持久化，设备/物理/回读/通知关联标志false；未操作硬件/实时UI，完整命令门槛false。


0.7.31离线验收：三组跨端共享契约、严格布尔域及ACK尾部覆盖；Node新增8项、Python新增8项，Web新增共享GATT/无Buffer回归，原生新增纯协议与假设备用例。统一Node263/Web26/Python3.8共238、原生969核心+276假设备生命周期+3独立SDK、研究403及严格类型/分层/签名构建通过，终态0。Python3.12完整238、研究403另行通过；验证快照、busy/来源切换、57与58隔离、坏ACK、取消前后、迟到响应及超时不重放。没有硬件/liveUI/厂商执行，完整命令门槛false。


0.7.31实际安装交付验证：Node tarball隔离安装后263项与严格TypeScript消费者通过；wheel隔离安装后238项通过，app_commands/app_handheld_stick/device/controller导入路径核对。Node104文件、wheel37模块、原生ZIP3文件与本次源码/签名构建逐字节一致，原生0.3.31/build34，未启动应用。没有npm发布或GitHub二进制Release。


## 0.7.32教程状态被动候选 / 原生0.3.32 build35

显式App来源下tutorialStatus（Python另有tutorial_status，原生appTutorialStatus）与kind=tutorial被动解码04:2B；保留步骤原值、完整32位无符号/有符号状态、9个数值标志、未知位与尾部，以及独立Java位移视图。未知步骤的源回退STEP_FINISH不是完成证明，bit30/31不解释为物理生命周期。缓存复制/不可变、观察者隔离，来源切换/断线清空；不发查询、订阅、ACK或04:2C，不结束查询或moveTo。本机布局/通知、请求关联及物理完成均未验收，完整命令和高级门槛仍false。契约见 docs/APP_TUTORIAL_STATUS.md（仓库根目录）。


0.7.32离线验收（2026-10-19）：八组跨端共享向量、256步骤及32单独置位核对；Node269/Web27/Python3.8与3.12各244、原生1290核心+285假设备生命周期+3独立SDK、研究两环境各403通过。统一检查终态0，严格类型、分层及签名构建通过。实际安装Node269+类型、wheel244通过；Node107文件、wheel38模块、原生ZIP3文件与源码/签名构建逐字节一致，Python四模块安装导入来源核对，原生0.3.32/build35未启动。没有蓝牙/实时UI/厂商代码执行，48项清单与完整命令/高级门槛仍false；没有npm发布或GitHub二进制Release。


## 04:40平衡调整请求与旧视图研究

固定六段61方法核对同命令发送/接收类、8个请求值、状态二进制字符串按十进制解析为0/1/10/11和非连续建议枚举；6个类外直接调用方法集中旧GimbalAdjustView。源attach可能关电机、20秒本地timer、错误/完成/超时发STOP，而detach未发STOP；不等于本机停止保证。见[平衡调整审计](tools/research/BALANCE_ADJUST.md)（仓库根目录）及protocol/research/ronin-balance-adjust-evidence.json。HG724入口、线上包层和物理效果未确认，未开放04:40 SDK收发、不替代balance_test/index37，无硬件/UI/厂商执行或高级新增，运行时仍0.7.32/0.3.32，全命令门槛false。


04:40研究验证（2026-10-19）：最终工具对固定输入独立提取两次，61方法/6类外直接调用方法证据JSON逐字节一致。新增12项，研究Python3.8/3.12各415通过；统一Node269/Web27/Python244/native1290+285+3及类型/分层/签名构建通过，终态0。Node/Python/Web/macOS目录与12a5025完全一致，0.7.32/0.3.32安装包不变，无SDK收发/高级新增或硬件/liveUI/厂商执行，全命令门槛false。


## 平衡入口型号条件与共享布局研究

固定六段30方法、4视图映射/3独立布局确认：有效所选项为HG724且BalanceCheck入口被调用时走GimbalVideoAdjustRS3，视频测试按钮GONE；两个新旧视频名共享同一布局/根类，不能连接为GimbalAdjustHG701的04:40发送。强制旧测试页可见说明是独立条件，不证明普通导航；限定字段引用扫描未建立旧调整页入口，也不证明固件不支持。见tools/research/BALANCE_ENTRY.md及protocol/research/ronin-balance-entry-evidence.json（仓库根目录）。没有新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.32/0.3.32，全部命令门槛false。


平衡入口研究验证（2026-10-19）：固定输入由最终工具独立提取两次，30方法、4视图映射/3独立布局和3个限定字段引用方法证据JSON逐字节一致。新增12项研究测试，两Python环境各427通过；统一Node269/Web27/Python244/native1290+285+3及类型/边界/签名构建通过，终态0。四端源码与ff18fcd相同，0.7.32/0.3.32安装包校验和不变；没有SDK收发/高级新增、硬件/liveUI/厂商执行。普通HG724菜单不走旧页不等于固件不支持04:40，全部命令门槛仍false。


## 01/07备份槽位的独立审计

固定APK新增3137条（01段2623/07段514）备份到准确code_off ULEB槽位及方法owner数值索引的核对，复用完整长度/异常表/不重叠校验；不恢复字符串/类型/原型身份，不输出可解析DEX。前128KiB在01另涉及3111条type_ids，在07涉及全部type/proto及部分field_ids，不能只补字符串表。见tools/research/CODE_SLOTS.md及protocol/research/ronin-code-slots-evidence.json（仓库根目录）。既有六段具名恢复/调用扫描范围不变，不把01/07加入其BANKS；运行时仍0.7.32/0.3.32，无SDK收发/高级新增、硬件/liveUI/厂商执行，完整门槛false。


01/07槽位审计验证（2026-10-19）：最终工具对真实固定输入独立提取两次，3137条备份数值槽位与归属、完整代码足迹、异常表和不重叠摘要一致。新增12项研究测试，Python3.8/3.12各439通过；统一Node269/Web27/Python244/native1290+285+3及严格类型/分层/签名构建通过，终态0。既有六段具名DEX固定哈希核对，四端源码与e1d10c0一致，0.7.32/0.3.32交付包校验和不变。没有生成01/07可解析DEX、运行厂商代码/实时UI或操作硬件，未新增SDK收发/高级功能，完整门槛false。


## 八段具名恢复与新增调用者

静态保护层线索结合自写SM4-ECB解码，八段完整保护容器源Adler32一致，独立OpenSSL核对全部1MiB前缀一致；01/07现已恢复可解析的类/方法/原型视图，共匹配52679条备份。源SHA1不匹配保护容器仍明确记录，派生校验和不冒充原始源码签名。旧六段[112,originalSize)元数据/代码字节一致、原文件不改写。新增01/07解析找到19方法/60稳定器直接引用，含激活库入口，未证明HG724/BLE路径或新增SDK发送。当前范围以tools/research/PREFIX_RESTORATION.md及protocol/research/ronin-prefix-restoration-evidence.json为准（仓库根目录）；旧六段扫描和“01/07未恢复”保留为历史证据，不自动提升旧结论为八段重审。运行时0.7.32/0.3.32，全App/全协议、全命令及高级门槛仍false，无硬件/liveUI/厂商代码执行。


八段具名恢复验收（2026-10-19）：最终标准库工具真实输入独立复现两次摘要一致；独立OpenSSL完整核对8×128KiB=1048576字节前缀。8段源保护容器Adler32均匹配、源SHA1均不匹配仍保留；六段旧语义字节/原文件不变。新增两段由Androguard遍历2938类、15383声明方法和14429含代码方法，19方法/60稳定器直接调用，未证明型号路径。新增16测试，Python3.8/3.12研究各455；统一Node269/Web27/Python244/native1290+285+3及类型/分层/签名构建通过，终态0。四端源码与e618a1a一致，运行时/安装包0.7.32/0.3.32不变，无SDK收发/高级新增、硬件/liveUI/厂商执行，完整门槛false。


## COMMON00:32激活状态源审计

八段56方法确认COMMON/ActiveStatus wire50（非ordinal20）、显式null Class、版本查询00与可能更新单例的版本响应，以及GET/SET/FAIL的版本/SN布局。Ver1_3与Ver13不同；新版SN最多复制16字节但分配仍用原始字节数+10。新增只读解析严格区分显式null与未知对象，旧通用解析器不改写。见tools/research/ACTIVATION.md及protocol/research/ronin-activation-evidence.json（仓库根目录）。00:32单列后当前清单49个命令或缺口条目，不是49项设备支持；无HG724/实际BLE/包层/网络业务及持久化验收，SDK收发未开放。运行时0.7.32/0.3.32，无设备激活/硬件/liveUI/厂商执行或高级新增，完整门槛false。


激活源审计验收（2026-10-19）：最终工具对固定八段真实输入独立提取两次，56方法及7个直接调用方法/2个版本setter调用方法摘要一致。新增16项，Python3.8/3.12研究各471通过；统一Node269/Web27/Python244/native1290+285+3及严格类型/分层/签名构建通过，终态0。00:32静态候选单列后当前清单49项，两门槛仍false。四端源码与3a992b6一致，0.7.32/0.3.32交付安装包不变；没有SDK收发、激活/硬件/liveUI/厂商执行或高级功能新增。


## COMMON00:32接收与查询缓存边界

八段39方法审计确认基础COMMON表isBlock=false/isMix=true，构造独立needsCcode=true，明文ACK先剥离返回码；显式null模型仍有按GIMBAL名称反射回退的条件路径。源激活状态类在null/长度/ACK检查前保存业务体，短版本响应可能先覆盖缓存，SDK不能照搬。八段精确invoke owner扫描7方法，5个类外方法无GIMBAL字段字面引用，不当成不支持或完整数据流证明。见[接收审计](tools/research/ACTIVATION_RECEIVE.md)（仓库根目录）及protocol/research/ronin-activation-receive-evidence.json。没有SDK收发、激活/硬件/liveUI/厂商执行或高级新增；运行时0.7.32/0.3.32、清单49项及两门槛false不变。

接收审计验收（2026-10-19）：最终工具真实固定输入独立提取两次，39方法/7直接查询调用方法证据逐字节一致；新增13项研究测试，Python3.8/3.12研究各484通过。统一离线Node269/Web27/Python244/native1290核心+285假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0。四端源码与318407a相同，0.7.32/0.3.32交付安装包不变；没有SDK收发、激活/硬件/liveUI/厂商执行或高级功能新增，全命令与高级门槛false。


## COMMON00:32 GET与V13/V14格式审计

固定bank05的34方法补GET响应/旧推送/V13设备信息与V14验证信息；全部八段哈希校验但本批方法范围仍仅05。GET的SN偏移8/9与推送1/2分开，源signed-byte十进制SN转换、V13/V14声明长度与实际复制/固定32字节区、标记51/54与版本枚举不同均保留。源V13处理可自动发135字节用户信息请求，工具不执行处理器或回复；isPushActivated直接存isEmpty不当激活成功。见[格式审计](tools/research/ACTIVATION_FORMATS.md)（仓库根目录）及protocol/research/ronin-activation-formats-evidence.json。HG724入口/实际会话/激活有效性/网络绑定未验收，无SDK收发/高级新增或硬件/liveUI/厂商执行；运行时0.7.32/0.3.32、清单49及两门槛false不变。

格式审计验收（2026-10-19）：最终工具对固定真实输入独立提取两次，34方法证据JSON逐字节一致；新增16项研究测试，Python3.8/3.12研究各500通过。统一离线Node269/Web27/Python244/native1290核心+285假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0。四端运行时代码与bcd24ac相同，0.7.32/0.3.32安装包未变，无SDK收发/激活/硬件/liveUI/厂商执行或高级新增，全命令与高级门槛false。


## HG724序列号CENTER路由与默认模块门槛

新增17方法与八段4个直接模块字段引用方法审计：HG724最近继承Ronin2的GimbalSerialNumber Getter，DataCenterActiveStatus/CENTER5/id7→COMMON00:32 GET，初始源Ver1_1体11不是GetVer00或GIMBAL/id0。源回调getPushSN在新读取空时可能保留旧值；通用基类module_type_唯一直接写为构造默认8，GIMBAL4/CENTER5默认均不通过V13/V14门槛，不等于固件不支持或排除native/反射修改。见[入口审计](tools/research/ACTIVATION_ENTRY.md)（仓库根目录）及protocol/research/ronin-activation-entry-evidence.json。只读源码路径提升为app-code-path，实际注册/会话/版本/设备/网络绑定未验收，SDK未开放；运行时0.7.32/0.3.32、清单49及全命令/高级门槛false。无硬件/liveUI/厂商执行或高级新增。

入口审计验收（2026-10-19）：最终工具对固定八段真实输入独立提取两次，17方法/4个直接模块字段引用方法证据JSON逐字节一致。新增13项研究测试，Python3.8/3.12研究各513通过；统一Node269/Web27/Python244/native1290核心+285假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0。四端运行时代码与d518ff2相同，0.7.32/0.3.32安装包不变。00:32只有继承只读源码路径提升为app-code-path，未新增SDK收发/激活/高级功能或硬件/liveUI/厂商执行；清单49项和两门槛false不变。


## 0.7.33 CENTER只读信息候选 / 原生0.3.33 build36

显式App来源新增getCenterActivationInfo（Python另有get_center_activation_info，原生RSGimbal继承同名selector），要求sourceVersion四种已知格式，无默认/OTHER/协商。固定E5/CENTER-id7、COMMON00:32 GET01/11与严格关联明文ACK；完整本次业务体解析active/date/SN原始值及源signed-decimal字符串、尾部，无旧SN缓存成功回退。GIMBAL04:32同命令号隔离，原生完成后恢复普通04路由；无激活/绑定/SET/FAIL/自动回复/重试/重放或高级新增。见[接口契约](docs/APP_CENTER_INFO.md)（仓库根目录）。设备/当前版本/布局/激活有效性未验收，全命令及高级门槛false，无硬件/liveUI/厂商执行。

0.7.33验收（2026-10-19）：十组四端共享契约及严格ACK/版本/长度检查，Node277/Web28/Python3.8与3.12各252、原生1562核心+299假设备生命周期+3独立SDK、研究两环境各513通过；统一检查终态0，严格类型/分层/签名构建通过。Node tarball隔离安装277项和类型通过；wheel隔离安装252项、三模块导入来源核对。Node110文件、wheel39模块、原生ZIP3文件与本次源码/签名构建逐字节一致，原生0.3.33/build36未启动。没有硬件/liveUI/厂商执行或npm发布/远端二进制Release；清单49、全命令/高级门槛false。


## macOS SDK GUI 0.3.34 / build37 (2026-10-20)

User requested polishing the existing SDK capabilities and making them callable from the macOS GUI. `RSSDKActions` is a typed/form adapter with 43 named App operations; `RSSDKPanel` calls the same public RSGimbal object as the original controls, displays ten passive status caches and raw degree-info messages. No packet construction, new protocol sends, new advanced composition or target-device proof. Native version0.3.34/build37; Node/Python/Web remain0.7.33. See docs/MACOS_SDK_PANEL.md. App profile is explicit, form edits never send, write permission resets per operation/request/disconnect, maintenance shows a concrete confirmation. Pending/errors/results remain distinct from physical completion. Native adapter tests use a recording proxy, not a Bluetooth manager. No real device or live connected GUI testing.

GUI delivery validation: default Python3.8 and explicit Python3.12 unified scripts both pass (Node277/Web28/SDK252/research558, native1562 core+299 fake lifecycle+3 standalone+267 GUI adapter checks). Optional offscreen AppKit layout covers all43 forms, without a Bluetooth manager. Native bundle0.3.34/build37 signed and built; production app/device not launched. GUI coverage/boundary guard verifies every existing public RSBleDevice method except construction has a GUI call site; source codecs and other ports remain unchanged. No all-command completion claim.


## 2026-10-20 returned user: existing SDK hardware session

The user explicitly confirmed unlocked/balanced/clear and present with power-off access, authorized low-speed small motion, and later reported no observed abnormality. This supersedes historical user-away hardware prohibitions for this session; it does not authorize activation writes or maintenance. Node0.7.33 direct cached UUID connection, feedback, Pan+3/Tilt+2/Roll+2 returns and initial-feedback cancellation tested. Roll settling error0.7 exceeds requested0.5 tolerance; no precision pass. Read-only23/26 initial requests parse; motor bulk04:32 incomplete, handle/6E timeout. Native GUI reads/feedback connect pass; Python3.12 Bleak UUID path scans and fails without advertisements; Web untested. See docs/HARDWARE_SESSION_2026-10-20.md for exact bounds and next steps. Preserve raw captures locally, no UUID/SN in Git. No device settings/calibration/reset/firmware program execution. Native0.3.35/build38 fixes finishApp missing idle/error status notification;1562+301+3+267 native checks, boundaries and signed build pass. Runtime Node/Python/Web unchanged0.7.33;49 entries and full-command/advanced gates remainfalse.
