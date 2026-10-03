import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
if (!process.env.SHARP_MODULE) throw new Error("Set SHARP_MODULE to the installed sharp entry point.");
const { default: sharp } = await import(pathToFileURL(process.env.SHARP_MODULE).href);
const [implementation, label] = process.argv.slice(2);
const source = path.join(root, "docs/ui-reference-package-20261003/app/project/screenshots/01-home.png");
const output = path.join(root, "docs/ui-reference-package-20261003/comparison");
await mkdir(output, { recursive: true });
const sourceFull = await sharp(source).extract({ left: 353, top: 65, width: 218, height: 440 })
  .resize({ width: 375 }).png().toBuffer();
const metadata = await sharp(implementation).metadata();
const isUserScreenshot = metadata.width === 440 && metadata.height > 800;
const crop = isUserScreenshot
  ? { left: 29, top: 74, width: 375, height: 698 }
  : { left: 0, top: 0, width: metadata.width, height: metadata.height };
const actualFull = await sharp(implementation).extract(crop).resize({ width: 375 }).png().toBuffer();
const sourceMeta = await sharp(sourceFull).metadata();
const actualMeta = await sharp(actualFull).metadata();
await sharp({ create: {
  width: 766, height: Math.max(sourceMeta.height, actualMeta.height), channels: 3, background: "#303030"
} }).composite([{ input: sourceFull, left: 0, top: 0 }, { input: actualFull, left: 391, top: 0 }])
  .png().toFile(path.join(output, `home-${label}-comparison.png`));
const sourceWheel = await sharp(source).extract({ left: 364, top: 109, width: 199, height: 192 })
  .resize(375, 362).png().toBuffer();
const actualWheel = isUserScreenshot
  ? await sharp(implementation).extract({ left: 45, top: 208, width: 343, height: 341 })
    .resize(375, 373).png().toBuffer()
  : actualFull;
const wheelMeta = await sharp(actualWheel).metadata();
await sharp({ create: { width: 766, height: Math.max(362, wheelMeta.height),
  channels: 3, background: "#303030" } })
  .composite([{ input: sourceWheel, left: 0, top: 0 }, { input: actualWheel, left: 391, top: 0 }])
  .png().toFile(path.join(output, `compass-${label}-comparison.png`));
console.log(`Comparison evidence: ${output}`);
