# AI developer handoff — rs4mini-ble-controller

Read this file first, then `README.md`, `node/API.md`, `docs/PROTOCOL.md`, and
`docs/DEVELOPMENT.md`. This document is intended to make development possible
without access to the original chat. Update these documents when behavior or
verification status changes.

## Objective and user decisions

- Provide an unofficial, direct BLE controller for **DJI RS 4 Mini**, initially on macOS.
- **Node.js is the authoritative implementation**; current package version is `0.5.0`.
- Preserve the existing Python, native macOS, and browser implementations, but do
  not claim feature parity. Python remains `0.2.1` and matches the early control API.
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
| `node/src/index.js` | Main `RS4Mini` API, Noble BLE lifecycle, command streaming, telemetry waits, position loop |
| `node/src/protocol.js` | Pure DUML encoder and CRCs |
| `node/src/telemetry.js` | BLE stream reassembly, CRC verification, `04:05` feedback decoder |
| `node/src/*.d.ts` | TypeScript declarations; keep synchronized with runtime |
| `node/examples/` | Offline tests and separate explicit hardware demos |
| `python/` | Legacy Bleak async controller, aliases, protocol and client tests |
| `macos/` | Objective-C/AppKit/CoreBluetooth control panel and build script |
| `web/` | Legacy Web Bluetooth module and HTML control page |
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
- `stop()` requests cancellation of an active `moveTo()` and sends neutral frames.
  The movement promise rejects with `RS4MINI_MOVE_CANCELLED` when the loop resumes.
  Do not assume the movement promise has already settled when `stop()` resolves.
- `moveTo()` rejects conflicting velocity, bounded-motion, recenter, and second
  position operations while active. Other motion combinations are not generally locked.
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

## Open issues and next engineering work

The current snapshot preserves the verified control implementation. Code review
identified the following follow-ups, which must not be described as already fixed:

1. Add deterministic failure/cancellation tests, especially stopping during an
   in-flight write, disconnect/reconnect listener cleanup, and close during a
   direct connection or GATT discovery.
2. Multi-axis `moveTo()` does not individually zero axes already within tolerance
   while another axis is still moving; it can continue to command `minSpeed` on
   a small residual error. Address before claiming multi-axis convergence quality.
3. The total move deadline can surface as a generic telemetry-wait timeout when
   it expires inside a wait, instead of `RS4MINI_MOVE_TIMEOUT`.
4. `moveToActive` is cleared before its final asynchronous stop completes; guard
   the cleanup interval against new motion commands. Current cancellation is
   cooperative and not a complete motion scheduling system.
5. `connect(timeoutMs)` does not bound every discovery/connection stage; strengthen
   cleanup and deadlines rather than assuming a hard end-to-end limit.
6. User callbacks can throw into notification processing; isolate errors before
   supporting untrusted callbacks or long-running services.
7. `moveFor()` is duration-bounded but its sleep is not cancellable and its later
   stop can interfere with a new command. Define general operation ownership.
8. Native stop writes are best-effort over BLE, not a firmware emergency-stop
   guarantee. No absolute-angle command, single-axis recenter, or disconnect
   auto-reconnect has been verified/implemented.
9. Python uses Python's rounding convention; JavaScript uses `Math.round`.
   Check half-step cases before claiming byte-for-byte parity.
10. Type declarations now pass a TypeScript 5.9.3 consumer smoke check
    (`node/examples/types-smoke.mts`), also configured in CI. Expand it when
    extending the public API; it does not prove runtime or every consumer type.

Choose follow-ups according to the next user request. Do not silently port all
changes to Python or expand into camera/vision work.

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
