import type { AxisValues, ByteBuffer } from "./types.js";

export function crc8(bytes: Uint8Array): number;
export function crc16(bytes: Uint8Array): number;
export function frame(
  sequence: number,
  commandSet: number,
  commandId: number,
  payload?: Uint8Array,
  flags?: number,
): ByteBuffer;
export function velocityFrame(sequence: number, velocity?: AxisValues): ByteBuffer;
export function stopFrame(sequence: number): ByteBuffer;
export function recenterFrame(sequence: number): ByteBuffer;
