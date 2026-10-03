import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
let definition;
let clock = 0;
let nextTimer = 1;
let navigations = [];
let scrolls = [];
const timers = new Map();
const source = file => readFileSync(new URL("../../../miniprogram/" + file, import.meta.url), "utf8");

globalThis.Page = page => { definition = page; };
globalThis.wx = {
  getStorageSync: () => [],
  setStorageSync: () => {},
  navigateTo: options => { navigations.push(options.url); },
  pageScrollTo: options => { scrolls.push(options.selector); }
};
globalThis.setTimeout = (callback, delay) => {
  const id = nextTimer++;
  timers.set(id, { callback, when: clock + delay });
  return id;
};
globalThis.clearTimeout = id => { timers.delete(id); };

function tick(duration) {
  const end = clock + duration;
  for (;;) {
    const ready = [...timers.entries()]
      .filter(([, timer]) => timer.when <= end)
      .sort((left, right) => left[1].when - right[1].when);
    if (!ready.length) break;
    const [id, timer] = ready[0];
    clock = timer.when;
    timers.delete(id);
    timer.callback();
  }
  clock = end;
}

function page(file) {
  require(file);
  return {
    ...definition,
    data: structuredClone(definition.data),
    setData(payload) { Object.assign(this.data, payload); }
  };
}

const home = page("../../../miniprogram/pages/index/index.js");
home.onLoad();
home.onShow();
assert.equal(home.data.showIntro, true);
assert.equal(home.data.motionRunning, false);
tick(3499);
assert.equal(home.data.motionRunning, false);
tick(1);
assert.equal(home.data.motionRunning, true);
tick(900);
assert.equal(home.data.showIntro, false);
assert.equal(timers.size, 0);

for (const slot of home.data.compassSlots) {
  const before = navigations.length;
  const beforeScroll = scrolls.length;
  home.selectCompassTopic({ currentTarget: { dataset: { id: slot.id } } });
  assert.equal(home.data.selectedFeatureMeta, slot.meta, "卦位元信息应与指针联动");
  assert.ok(slot.meta && slot.meta.includes(" · "), "不得用功能说明替代来源卦位信息");
  home.openCompassFeature();
  home.openCompassFeature();
  assert.equal(timers.size, 1, "重复点击不能叠加延时跳转");
  assert.equal(home.data.casting, true);
  const blocked = slot.id === "bazi" ? "daily" : "bazi";
  home.selectCompassTopic({ currentTarget: { dataset: { id: blocked } } });
  assert.equal(home.data.selectedFeatureId, slot.id, "旋转期间不能换入口");
  home.onFeatureTap({ currentTarget: { dataset: { id: blocked } } });
  assert.equal(navigations.length, before, "列表入口不能绕过旋转保护");
  assert.equal(scrolls.length, beforeScroll);
  tick(2499);
  assert.equal(navigations.length, before);
  assert.equal(scrolls.length, beforeScroll);
  tick(1);
  assert.equal(home.data.casting, false);
  assert.equal(timers.size, 0);
  if (slot.id === "bazi") {
    assert.equal(scrolls.at(-1), "#chart-form");
    assert.equal(navigations.length, before);
  } else {
    const route = ["prayer", "wish"].includes(slot.id) ? "prayer/prayer" : "tools/tools";
    assert.equal(navigations.length, before + 1);
    assert.equal(navigations.at(-1), `/pages/${route}?mode=${slot.id}`);
  }
}

for (const lifecycle of ["onHide", "onUnload"]) {
  home.onLoad();
  home.selectCompassTopic({ currentTarget: { dataset: { id: "daily" } } });
  home.openCompassFeature();
  assert.equal(timers.size, 3);
  const before = navigations.length;
  home[lifecycle]();
  assert.equal(timers.size, 0);
  tick(5000);
  assert.equal(navigations.length, before, "离开首页后不能再跳转");
  assert.equal(home.data.motionPaused, true);
  assert.equal(home.data.casting, false);
  assert.equal(home.data.showIntro, false);
  home.onShow();
  assert.equal(home.data.motionPaused, false);
}

const result = page("../../../miniprogram/pages/result/result.js");
assert.equal(result.data.dayMasterStem, "");
result.onHide();
assert.equal(result.data.motionPaused, true);
result.onShow();
assert.equal(result.data.motionPaused, false);
assert.match(source("pages/result/result.wxml"), /motionPaused/);
assert.match(source("pages/index/index.wxml"), /home-intro[^>]*aria-hidden="true"/);
assert.match(source("pages/index/index-effects.wxss"), /\.home-intro\s*\{[^}]*pointer-events:\s*none/);
assert.match(source("styles/motion.wxss"), /prefers-reduced-motion:\s*reduce/);
const theme = source("app.wxss").toLowerCase();
for (const color of ["#100807", "#f0a886", "#f5ede6", "#d96b4f", "#b84a30"]) {
  assert.ok(theme.includes(color), `缺少参考配色：${color}`);
}
for (const file of ["pages/index/index.wxml", "pages/tools/tools.wxml", "pages/prayer/prayer.wxml"]) {
  assert.ok(source(file).includes("button-sheen"));
  assert.ok(!source(file).includes('color="#ad7b64"') && !source(file).includes('color="#b95034"'));
}
const homeTemplate = source("pages/index/index.wxml");
assert.match(homeTemplate, /class="hero-meta serif"[^>]*>\{\{selectedFeatureMeta\}\}/);
assert.match(homeTemplate, /class="form-fields"/, "输入区保留来源细边框行组");
assert.match(homeTemplate, /compass-wedge[^>]*src="\/assets\/compass\/wedge.png"/);
const homeStyle = source("pages/index/index-home.wxss");
assert.match(homeStyle, /\.hero-subtitle\s*\{[^}]*color:\s*var\(--color-text-muted\)/);
assert.match(homeStyle, /\.compass-center\[disabled\]/, "旋转时不能变成原生灰色按钮");
assert.match(homeStyle, /\.feature-item:last-child\s*\{[^}]*border-bottom:\s*0/);
const formStyle = source("pages/index/index-form.wxss");
assert.match(formStyle, /\.calendar-field\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
assert.match(formStyle, /\.form-fields\s*\{[^}]*border:\s*1rpx solid/);
const wedge = readFileSync(new URL("../../../miniprogram/assets/compass/wedge.png", import.meta.url));
assert.deepEqual([wedge.readUInt32BE(16), wedge.readUInt32BE(20)], [1000, 1000]);
for (const layer of ["plate", "structure", "trigrams", "gua", "jieqi", "dizhi", "orbit", "outer"]) {
  const png = readFileSync(new URL(`../../../miniprogram/assets/compass/layers/${layer}.png`, import.meta.url));
  assert.equal(png.subarray(1, 4).toString(), "PNG", `图层无效：${layer}`);
}
for (const effect of ["day-master", "intro", "star"]) {
  const png = readFileSync(new URL(`../../../miniprogram/assets/compass/effects/${effect}.png`, import.meta.url));
  assert.equal(png.subarray(1, 4).toString(), "PNG", `特效素材无效：${effect}`);
  const expectedSize = effect === "intro" ? [804, 1748] : effect === "star" ? [64, 64] : [240, 240];
  assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], expectedSize, `特效尺寸错误：${effect}`);
}
console.log(JSON.stringify({ validated: true, compassRoutes: 8, lifecycle: true }));
