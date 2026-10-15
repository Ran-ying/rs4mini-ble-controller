import { RS4Mini } from "../src/index.js";

const gimbal = new RS4Mini();
try {
  const name = await gimbal.connect();
  console.log("connected:", name);
  await gimbal.stop();
  console.log("neutral stop test complete");
} finally {
  await gimbal.close();
}
