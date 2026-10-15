// Preserve Buffer return values in Node; use ordinary Uint8Array in browsers.
export function bytes(input = 0) {
  if (globalThis.Buffer) return typeof input === 'number' ? globalThis.Buffer.alloc(input) : globalThis.Buffer.from(input);
  return new Uint8Array(input);
}
export const view = value => new DataView(value.buffer, value.byteOffset, value.byteLength);
export const hex = value => Array.from(value, byte => byte.toString(16).padStart(2, '0')).join('');
export function concat(chunks) {
  const output = bytes(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) { output.set(chunk, offset); offset += chunk.length; }
  return output;
}
