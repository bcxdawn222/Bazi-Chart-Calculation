import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const moduleFile = path.join(root, "tmp/node_modules/miniprogram-automator/out/index.js");
const { default: automator } = await import(pathToFileURL(moduleFile).href);
const output = path.join(root, "docs/ui-reference-20261002/implementation");
await mkdir(output, { recursive: true });
let mini;
const evidence = [];
const timeoutSeconds = Number(process.env.UI_CAPTURE_TIMEOUT_SECONDS || 130);
if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 5) throw new Error("Invalid capture timeout");
const timeout = setTimeout(() => {
  console.error("Visual capture timeout; no visual acceptance claimed.");
  process.exit(1);
}, timeoutSeconds * 1000);
try {
  console.log("Connecting to WeChat automation.");
  mini = await automator.connect({ wsEndpoint: "ws://127.0.0.1:9420" });
  mini.on("exception", error => console.error("Simulator exception:", error));
  console.log("Connected; reading current page.");
  const current = await mini.currentPage();
  console.log("Current route:", current?.path || "(no page)");
  if (process.env.UI_CAPTURE_DIAGNOSE === "1") {
    const info = await mini.systemInfo();
    console.log("Simulator:", JSON.stringify({
      width: info.windowWidth, height: info.windowHeight,
      SDKVersion: info.SDKVersion, platform: info.platform
    }));
    console.log("Compass rendered:", Boolean(current && await current.$(".compass-center")));
    process.exitCode = 0;
  } else {
    const home = current && current.path === "pages/index/index"
      ? current : await mini.reLaunch("/pages/index/index");
    if (!home) throw new Error("Home route was not returned by the simulator.");
    console.log("Home route:", home.path);
    await home.waitFor(".compass-center");
    await home.waitFor(4600);
    console.log("Compass rendered; capturing home.");
    await mini.screenshot({ path: path.join(output, "home.png") });
    evidence.push({ name: "home", path: home.path });
    const center = await home.$(".compass-center");
    if (!center) throw new Error("Compass control was not returned by the simulator.");
    await center.tap();
    await home.waitFor(2900);
    await mini.screenshot({ path: path.join(output, "form.png") });
    evidence.push({ name: "form", path: home.path });
    // 仅导航与截图，不提交表单、建立订单或清理用户存储。
    for (const mode of ["compatibility", "naming", "daily"]) {
      const page = await mini.reLaunch(`/pages/tools/tools?mode=${mode}`);
      if (!page) throw new Error(`Tool route was not returned: ${mode}`);
      await page.waitFor(".tool-title");
      await mini.screenshot({ path: path.join(output, `${mode}.png`) });
      evidence.push({ name: mode, path: page.path });
    }
    const prayer = await mini.reLaunch("/pages/prayer/prayer");
    if (!prayer) throw new Error("Prayer route was not returned by the simulator.");
    await prayer.waitFor(".prayer-title");
    await mini.screenshot({ path: path.join(output, "prayer.png") });
    evidence.push({ name: "prayer", path: prayer.path });
    await mini.reLaunch("/pages/index/index");
    await writeFile(path.join(output, "capture.json"), JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify(evidence));
  }
} finally {
  clearTimeout(timeout);
  if (mini) await mini.disconnect();
}
