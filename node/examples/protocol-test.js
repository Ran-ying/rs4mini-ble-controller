import assert from "node:assert/strict";
import { recenterFrame, stopFrame, velocityFrame } from "../src/protocol.js";

const expected = "551604fc020400010004010004000400040000027705";
assert.equal(stopFrame(0x0100).toString("hex"), expected);
assert.equal(velocityFrame(1, { pan: 0, tilt: 0, roll: 0 })[9], 0x04);
assert.equal(velocityFrame(1, { pan: 0, tilt: 0, roll: 0 })[10], 0x01);
assert.equal(recenterFrame(1)[9], 0x04);
assert.equal(recenterFrame(1)[10], 0x4c);
console.log("protocol golden vector OK:", expected);
