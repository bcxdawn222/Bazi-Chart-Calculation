import { chromium } from "playwright";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const dir = dirname(fileURLToPath(import.meta.url));
const preview = pathToFileURL(join(dir, "preview.html")).href;
const shots = [
  ["base", "analysis-base.png"],
  ["locked", "analysis-locked.png"],
  ["pending", "analysis-pending.png"],
  ["paid", "analysis-paid.png"],
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 430, height: 1400 }, deviceScaleFactor: 2 });
for (const [state, file] of shots) {
  await page.goto(`${preview}?state=${state}`, { waitUntil: "load" });
  const frame = page.locator(".stage.active .phone");
  await frame.waitFor({ state: "visible" });
  await frame.screenshot({ path: join(dir, file) });
}
await browser.close();
