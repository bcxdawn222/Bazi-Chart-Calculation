import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
let definition;
let storage = {};
let modal;
let writes = 0;
let navigations = 0;
let scroll;
globalThis.Page = page => { definition = page; };
globalThis.getApp = () => ({ globalData: {} });
globalThis.wx = {
  getStorageSync: key => storage[key],
  setStorageSync: (key, value) => { writes++; storage[key] = value; },
  removeStorageSync: key => { writes++; delete storage[key]; },
  showModal: options => { modal = options; },
  showToast: () => {},
  setNavigationBarTitle: () => {},
  navigateTo: () => { navigations++; },
  pageScrollTo: options => { scroll = options.selector; }
};

function page(path, data = {}) {
  require(path);
  return Object.assign({}, definition, {
    data: structuredClone({ ...definition.data, ...data }),
    setData(payload, callback) {
      Object.assign(this.data, payload);
      if (callback) callback.call(this);
    }
  });
}

const home = page("../../miniprogram/pages/index/index.js");
for (const input of [{ location: "abc" }, { location: "200" }, { date: "2023-02-29" }]) {
  Object.assign(home.data, { date: "1990-01-01", location: "120" }, input);
  const before = JSON.stringify(storage);
  home.submitChart();
  assert.ok(home.data.fieldErrors[Object.keys(input)[0]]);
  for (const [key, value] of Object.entries(input)) assert.equal(home.data[key], value);
  assert.equal(JSON.stringify(storage), before);
  assert.equal(navigations, 0);
}
Object.assign(home.data, { date: "2024-02-29", location: "120", dateType: "solar", fieldErrors: {} });
const leapNavigations = navigations;
home.submitChart();
assert.equal(home.data.date, "2024-02-29");
assert.ok(!home.data.fieldErrors.date);
assert.ok(navigations > leapNavigations);
assert.equal(storage.latestChartResult.normalizedTime.longitude, 120);
assert.equal(storage.latestChartResult.normalizedTime.source.month, 2);
assert.equal(storage.latestChartResult.normalizedTime.source.day, 29);

const calendar = require("../../miniprogram/core/calendar.js");
for (const location of ["", "   "]) {
  const normalized = calendar.normalizeBirthInput({
    date: "1990-01-01 12:00",
    dateType: "solar",
    location,
    ziHourMode: "early"
  });
  assert.equal(normalized.longitude, 120, `空经度应保持默认 120，实际=${normalized.longitude}`);
}
Object.assign(home.data, { date: "1990-01-01", location: "", fieldErrors: {} });
home.submitChart();
assert.ok(!home.data.fieldErrors.location);
assert.equal(home.data.location, "");
assert.equal(storage.latestChartResult.normalizedTime.longitude, 120);

storage = { recentCharts: [{ name: "甲" }, { name: "乙" }], latestChartResult: { keep: true } };
home.data.recentCharts = storage.recentCharts;
home.clearRecent();
assert.equal(storage.recentCharts.length, 2);
modal.success({ confirm: false });
assert.equal(home.data.recentCharts.length, 2);
home.clearRecent();
modal.success({ confirm: true });
assert.equal(storage.recentCharts, undefined);
assert.equal(home.data.recentCharts.length, 0);
assert.deepEqual(storage.latestChartResult, { keep: true });

const tools = page("../../miniprogram/pages/tools/tools.js", {
  mode: "compatibility", leftName: "甲", rightName: "乙",
  leftLocationLabel: "北京", rightLocationLabel: "上海"
});
const compatibility = require("../../miniprogram/core/features/compatibility.js");
const originalBuild = compatibility.build;
let builds = 0;
compatibility.build = (...args) => { builds++; return originalBuild(...args); };
const valid = structuredClone(tools.data);
for (const input of [
  { leftDate: "" }, { rightDate: "" }, { leftLocation: "abc" }, { rightLocation: "200" },
  { leftDate: "2023-02-29" }, { rightDate: "2051-01-01" },
  { leftTime: "24:00" }, { rightTime: "" }
]) {
  tools.data = structuredClone({ ...valid, ...input });
  modal = null;
  const before = writes;
  tools.runTool();
  const field = Object.keys(input)[0];
  assert.ok(tools.data.fieldErrors[field], `缺少字段错误：${field}=${input[field]}`);
  assert.equal(tools.data[field], input[field]);
  assert.equal(modal, null);
  assert.equal(builds, 0);
  assert.equal(writes, before);
}
tools.data = structuredClone(valid);
tools.runTool();
assert.equal(builds, 1);
assert.ok(tools.data.result.left.pillarList.length === 4);
tools.data = structuredClone({ ...valid, leftDate: "2024-02-29" });
tools.runTool();
assert.equal(builds, 2);
assert.ok(!tools.data.fieldErrors.leftDate);
assert.ok(tools.data.result.left.pillarList.length === 4);
compatibility.build = originalBuild;

for (const mode of ["question", "liuyao"]) {
  for (const input of [{ date: "2023-02-29" }, { time: "24:00" }]) {
    tools.data = { ...valid, mode, question: "出行", date: "2026-10-01", time: "12:00", ...input };
    modal = null;
    tools.runTool();
    assert.ok(tools.data.fieldErrors[Object.keys(input)[0]], `${mode}字段错误`);
    assert.equal(modal, null);
  }
}
tools.onTimeChange({ detail: { value: "12:00" } });
assert.ok(!tools.data.fieldErrors.time);
tools.data = { ...valid, mode: "naming", surname: "", givenName: "" };
tools.runTool();
assert.equal(tools.data.namingReady, false);
assert.ok(tools.data.namingHint);

const prayer = page("../../miniprogram/pages/prayer/prayer.js");
const before = writes;
prayer.createRecord();
assert.ok(prayer.data.fieldErrors.name && prayer.data.fieldErrors.wish);
assert.equal(writes, before);
prayer.onInput({ currentTarget: { dataset: { field: "name" } }, detail: { value: "甲" } });
assert.ok(!prayer.data.fieldErrors.name);
assert.ok(prayer.data.fieldErrors.wish);

const result = page("../../miniprogram/pages/result/result.js");
result.onTabChange({ currentTarget: { dataset: { tab: "ziwei" } } });
assert.equal(scroll, "#section-ziwei");
delete storage.latestChartResult;
result.onLoad();
assert.equal(result.data.hasResult, false);
const format = require("../../miniprogram/core/format.js");
const goodChart = format.buildChart({
  date: "1990-01-01 12:00", dateType: "solar", location: "120", gender: "male"
});
for (const corrupt of [
  chart => { chart.bazi.details.pillars = null; },
  chart => { chart.ziwei.palaces[0].mainStars = null; },
  chart => { chart.ziwei.palaces[0].relatedPalaces = null; },
  chart => { delete chart.normalizedTime.solar; }
]) {
  storage.latestChartResult = structuredClone(goodChart);
  corrupt(storage.latestChartResult);
  modal = null;
  assert.doesNotThrow(() => result.onLoad(), "损坏缓存应提示重新排盘，不能使页面异常");
  assert.equal(storage.latestChartResult, undefined);
  assert.ok(modal);
}

const api = require("../../miniprogram/core/api.js");
let prayerReply;
let wishReply;
api.listPrayers = callback => { prayerReply = callback; };
api.listWishes = callback => { wishReply = callback; };
storage.localPrayerRecords = Array.from({ length: 30 }, (_, index) => ({
  id: `wish-${index}`, type: "wish", status: "进行中"
}));
prayer.data.mode = "prayer";
prayer.loadRemote("prayer");
prayerReply({ ok: true, items: [{
  id: "remote-prayer", status: "active", payload: { name: "甲", type: "prayer" }
}] });
assert.ok(storage.localPrayerRecords.some(item => item.remoteId === "remote-prayer"), "其他模式满额不能挤掉当前模式记录");
prayer.loadRemote("prayer");
prayer.switchMode({ currentTarget: { dataset: { mode: "wish" } } });
wishReply({ ok: true, items: [] });
prayerReply({ ok: true, items: [{ id: "old-prayer", status: "active", payload: { type: "prayer" } }] });
assert.ok(prayer.data.records.every(item => item.type === "wish"), "旧模式的响应不能覆盖新模式列表");
assert.equal(prayer.data.mode, "wish");

prayer.data.mode = "prayer";
storage.localPrayerRecords = [{ id: "new", remoteId: "remote-new", type: "prayer", status: "进行中" }];
prayer.loadRemote("prayer");
api.updatePrayer = (id, status, callback) => callback({ ok: true });
prayer.completeRecord({ currentTarget: { dataset: { id: "new" } } });
prayerReply({ ok: true, items: [{ id: "remote-new", status: "active", payload: { id: "new", type: "prayer" } }] });
assert.equal(prayer.data.records[0].status, "已完成", "先发出的列表请求不能撤销刚完成的操作");

const sharedTools = Object.assign({}, tools, { data: { ...valid, mode: "daily" } });
let relaunched = "";
wx.navigateBack = options => { if (options.fail) options.fail({ errMsg: "no previous page" }); };
wx.reLaunch = options => { relaunched = options.url; };
sharedTools.goToChart();
assert.equal(relaunched, "/pages/index/index", "分享直达工具页时仍能进入排盘首页");
const source = file => readFileSync(new URL("../../miniprogram/" + file, import.meta.url), "utf8");
const template = source("pages/result/result.wxml");
for (const binding of ["section-bazi", "section-ziwei", "mainStarsText", "auxiliaryStarsText", "daxian", "transformations"]) {
  assert.ok(template.includes(binding), `结果页字段保留：${binding}`);
}
assert.ok(source("pages/tools/tools.wxml").includes("empty-state"));
const base = source("pages/result/result-base.wxss");
assert.match(base, /\.result-topline\s*\{[^}]*min-height:\s*var\(--touch-min\)/);
assert.match(base, /\.palace-aux\s*\{[^}]*font-size:\s*32rpx/);
assert.match(base, /\.profile-avatar\s*\{[^}]*flex-shrink:\s*0/, "长名称不应压缩头像");
assert.match(base, /\.profile-copy\s*\{[^}]*flex:\s*1/, "名称应使用头像与状态之间的剩余空间");
assert.match(base, /\.profile-status\s*\{[^}]*flex-shrink:\s*0/, "长名称不应压缩状态标记");
assert.match(base, /\.profile-status\s*\{[^}]*white-space:\s*nowrap/, "状态标记不应被拆成多行");
assert.match(base, /\.profile-name,\s*\.profile-meta\s*\{[^}]*overflow-wrap:\s*anywhere/, "无空格长文本应能在名称区域换行");
console.log(JSON.stringify({ validated: true }));
