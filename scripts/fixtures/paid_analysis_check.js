const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const format = require("../../miniprogram/core/format");
const api = require("../../miniprogram/core/api");

const ROOT = path.join(__dirname, "../..");
const DISCLAIMER = "传统文化研究与娱乐参考";
const FORBIDDEN = [/alipay/i, /requestAlipay/, /支付宝收银台/];

const result = format.buildChart({
  dateType: "solar",
  date: "1990-01-01 12:00",
  location: "116.40",
  gender: "male",
  realSolarTime: true,
  ziHourMode: "early",
  leapMonth: false,
});

assert.ok(format.isValidChart(result));
assert.equal(Object.values(result.analysis).filter(Boolean).length, 5);
Object.values(result.analysis).forEach(function (text) {
  assert.ok(text.includes(DISCLAIMER), text);
  assert.ok(text.includes("日柱") || text.includes("五行"), text);
});
assert.ok(Object.values(result.analysis).some(function (text) {
  return text.includes(result.bazi.pillars.day);
}));
assert.ok(Object.values(result.analysis).some(function (text) {
  return text.includes("五行") && text.includes("木");
}));

const chartKey = format.buildChartKey(result);
assert.match(chartKey, /^[A-Za-z0-9_-]{8,64}$/);
assert.equal(chartKey, [
  "ck",
  result.normalizedTime.solar.year,
  result.normalizedTime.solar.month,
  result.normalizedTime.solar.day,
  result.normalizedTime.hour,
  result.normalizedTime.minute,
  result.input.gender,
  result.normalizedTime.ziHourMode || result.input.ziHourMode || "early",
  result.input.dateType || "solar",
].join("-").slice(0, 64));

[
  "miniprogram/pages/result/result.wxml",
  "miniprogram/pages/result/result.js",
  "miniprogram/core/api.js",
].forEach(function (rel) {
  const source = fs.readFileSync(path.join(ROOT, rel), "utf8");
  FORBIDDEN.forEach(function (pattern) {
    assert.equal(pattern.test(source), false, rel + " 含禁止字段 " + pattern);
  });
});

const indexSource = fs.readFileSync(path.join(ROOT, "miniprogram/pages/index/index.js"), "utf8");
assert.equal(/id:\s*["']consult["']/.test(indexSource), false, "首页入口不含咨询");
assert.equal(typeof api.createOrder, "function");
assert.equal(typeof api.listOrders, "function");
assert.equal(typeof api.prepareOrderPayment, "function");
assert.equal(typeof api.getOrder, "function");
assert.equal(typeof api.createAnalysisOrder, "function");
assert.equal(typeof api.getAnalysisOrder, "function");
assert.equal(typeof api.getAnalysisReport, "function");
assert.equal(typeof api.generateAnalysisReport, "function");

let definition;
const storage = { latestChartResult: result };
const appState = { globalData: { chartResult: result } };
global.Page = function (page) { definition = page; };
global.getApp = function () { return appState; };
global.wx = {
  getStorageSync: function (key) { return storage[key] || null; },
  setStorageSync: function (key, value) { storage[key] = value; },
  removeStorageSync: function (key) { delete storage[key]; },
  showModal: function () {},
  pageScrollTo: function () {},
  requestPayment: function (options) { options.fail({ errMsg: "requestPayment:fail cancel" }); }
};

require("../../miniprogram/pages/result/result");
const page = Object.assign({
  data: Object.assign({}, definition.data),
  setData: function (payload) { Object.assign(this.data, payload); }
}, definition);

page.onLoad();
assert.equal(page.data.analysis.length, 5);
assert.ok(page.data.analysis.every(function (item) { return item.text.includes(DISCLAIMER); }));
assert.equal(typeof page.unlockAnalysis, "function");
assert.equal(typeof page.continueAnalysisPayment, "function");
assert.equal(typeof page.retryGenerate, "function");
assert.equal(page.data.detailedSections.length, 0);
assert.equal(page.data.analysisPaid, false);

let createdPayload = null;
let generated = false;
api.environmentStatus = function () { return { online: true, baseUrl: "https://example.invalid", reason: "" }; };
api.userMessage = function (reason) { return reason; };
api.login = function (callback) { callback({ ok: true, message: "" }); };
api.getConfig = function (callback) {
  callback({ ok: true, data: { analysis: { enabled: true, price_cents: 19900, reason: "" } } });
};
api.getAnalysisOrder = function (key, callback) { callback({ ok: true, data: { item: null } }); };
api.getAnalysisReport = function (key, callback) {
  callback({
    ok: true,
    data: { item: { chart_key: key, paid: false, sections: {}, source: "pending", reason: "" } }
  });
};
api.createAnalysisOrder = function (payload, callback) {
  createdPayload = payload;
  callback({
    ok: true,
    data: {
      item: {
        id: "order-analysis", kind: "analysis", chart_key: payload.chart_key,
        payment_status: "pending", service_status: "pending"
      }
    }
  });
};
api.prepareOrderPayment = function (orderId, callback) {
  callback({
    ok: true,
    data: { payment: { timeStamp: "1", nonceStr: "n", package: "prepay_id=x", signType: "RSA", paySign: "s" } }
  });
};
api.getOrder = function (orderId, callback) {
  callback({ ok: true, data: { item: { id: orderId, payment_status: "pending" } } });
};
api.generateAnalysisReport = function (payload, callback) {
  generated = true;
  callback({
    ok: true,
    data: {
      item: {
        chart_key: payload.chart_key, paid: true, source: "ai", reason: "",
        sections: {
          wealth: "假财富", marriage: "假婚姻", career: "假运程",
          personality: "假性格", health: "假健康"
        }
      }
    }
  });
};

page.loadAnalysisUnlock();
assert.equal(page.data.analysisUnlockEnabled, true);
assert.equal(page.data.analysisPriceText, "199.00");
assert.equal(page.data.analysis.length, 5);

page.unlockAnalysis();
assert.equal(createdPayload.chart_key, chartKey);
assert.equal(page.data.analysisPaid, false);
assert.equal(page.data.detailedSections.length, 0);
assert.equal(page.data.analysisCanContinue, true);
assert.ok(page.data.analysisReason.includes("取消"));
assert.equal(generated, false);

wx.requestPayment = function (options) { options.success(); };
page.continueAnalysisPayment();
assert.equal(page.data.analysisPaid, false);
assert.equal(page.data.detailedSections.length, 0);
assert.equal(generated, false);
page.stopAnalysisPoll();

api.getOrder = function (orderId, callback) {
  callback({ ok: true, data: { item: { id: orderId, payment_status: "paid" } } });
};
api.getAnalysisReport = function (key, callback) {
  callback({
    ok: true,
    data: {
      item: {
        chart_key: key, paid: false, source: "pending", reason: "未支付",
        sections: { wealth: "不应展示" }
      }
    }
  });
};
api.generateAnalysisReport = function (payload, callback) {
  generated = true;
  callback({
    ok: true,
    data: {
      item: {
        chart_key: payload.chart_key, paid: false, sections: {},
        source: "pending", reason: "该命盘尚未支付详细解读"
      }
    }
  });
};
generated = false;
page.pollAnalysisOrder("order-analysis", 0);
assert.equal(generated, true);
assert.equal(page.data.detailedSections.length, 0);
assert.ok(page.data.analysis.every(function (item) { return !item.text.includes("不应展示"); }));

page.onUnload();
console.log(JSON.stringify({ validated: true }));
