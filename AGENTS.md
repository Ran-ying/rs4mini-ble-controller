# AI developer handoff — rs4mini-ble-controller

Read this file first, then `README.md`, `node/API.md`, `docs/PROTOCOL.md`, and
`docs/DEVELOPMENT.md`. This document is intended to make development possible
without access to the original chat. Update these documents when behavior or
verification status changes.

## Objective and user decisions

- Provide an unofficial, direct BLE controller for **DJI RS 4 Mini**, initially on macOS.
- **Node.js is the authoritative implementation**; current package version is `0.7.0`.
- The user subsequently requested completion of all existing ports. Python is now
  `0.7.0`, Web shares the JS core, and the native panel is `0.3.0`. Describe the
  documented feature differences; do not claim identical APIs or hardware proof.
- After that delivery, the user requested the remaining **non-camera** capabilities
  under the same autonomous/offline conditions. Expansion work is in progress;
  see `docs/EXPANSION_PLAN.md`. The 0.7.0 source checkpoint and its remaining
  verification gates are recorded in `docs/PROJECT_STATUS.md`.
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
| `node/src/controller.js` | Shared motion ownership, deadlines, lifecycle, telemetry waits and position loop |
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

Further static research downloaded the official Ronin 2.2.2/7096 APK into ignored
`work/research/`. `docs/RESEARCH_NEXT.md` records its hash and candidate gimbal
classes; only the AppGuard wrapper and raw class names were inspected. Business
payload/request/model-branch reconstruction is unfinished. The APK was not
installed or executed. Do not infer RS 4 Mini command layouts from class names.

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
