const api = require("../../miniprogram/core/api");
const consultation = require("../../miniprogram/pages/tools/consultation");

global.wx = {
  requestPayment: function () {},
};

const responses = {
  config: {
    ok: true,
    data: {
      consultation: { enabled: true },
      payment: { enabled: true },
      ai: { enabled: false },
    },
  },
  experts: {
    ok: true,
    data: {
      items: [
        { id: "expert-online", status: "online", price_cents: 19900 },
        { id: "expert-offline", status: "offline", price_cents: 19900 },
      ],
    },
  },
  schedules: {
    ok: true,
    data: {
      items: [{
        id: "schedule-one",
        expert_id: "expert-online",
        starts_at: "2026-09-02T09:00:00+08:00",
        ends_at: "2026-09-02T10:00:00+08:00",
        status: "available",
      }],
    },
  },
  orders: { ok: true, data: { items: [] } },
};

api.getConfig = callback => callback(responses.config);
api.listExperts = callback => callback(responses.experts);
api.listSchedules = (expertId, callback) => callback(responses.schedules);
api.listOrders = callback => callback(responses.orders);
api.createOrder = (payload, callback) => callback({ ok: true, data: { item: { id: "order-one" } } });
let prepareAttempts = 0;
api.prepareOrderPayment = (orderId, callback) => {
  prepareAttempts += 1;
  callback({
    ok: true,
    data: {
      payment: {
        timeStamp: String(prepareAttempts),
        nonceStr: "nonce",
        package: "prepay_id=test",
        signType: "RSA",
        paySign: "sign",
      },
    },
  });
};
api.getOrder = (orderId, callback) => callback({
  ok: true,
  data: { item: { id: orderId, payment_status: "paid", service_status: "pending" } },
});

let paymentAttempts = 0;
wx.requestPayment = function (options) {
  paymentAttempts += 1;
  if (paymentAttempts === 1) options.fail({ errMsg: "requestPayment:fail cancel" });
  else options.success();
};

const page = Object.assign({
  data: Object.assign({}, consultation.initialData),
  setData: function (payload) { this.data = Object.assign({}, this.data, payload); },
}, consultation.methods);

page.consultActive = true;
page.loadConsultationData();
page.selectExpert({ currentTarget: { dataset: { id: "expert-online" } } });
page.selectSchedule({ currentTarget: { dataset: { id: "schedule-one" } } });
page.payConsultation();
page.retryPayment({ currentTarget: { dataset: { id: "order-one" } } });

const normalFlow = page.data.experts.length === 1
    && page.data.availableSchedules.length === 1
    && page.data.availableSchedules[0].displayTime.includes("至")
    && paymentAttempts === 2
    && prepareAttempts === 2
    && page.data.orderStatus === "已支付"
    && page.data.paymentLoading === false;

const assert = require("node:assert/strict");
assert.ok(normalFlow);
let orderReply;
api.createOrder = (payload, callback) => { orderReply = callback; };
page.payConsultation();
page.onHide();
orderReply({ ok: true, data: { item: { id: "hidden-order" } } });
assert.equal(page.data.canRetryCurrentPayment, true, "创建订单后隐藏页面仍应保留继续支付入口");
assert.equal(page.data.paymentLoading, false);
page.onShow();
assert.equal(page.data.canRetryCurrentPayment, true);

const fs = require("node:fs");
const vm = require("node:vm");
let loginRequest;
let loginAttempts = 0;
const store = {};
const isolated = { exports: {} };
const sandboxWx = {
  getStorageSync: key => store[key],
  setStorageSync: (key, value) => { store[key] = value; },
  removeStorageSync: key => { delete store[key]; },
  login: options => { loginAttempts++; options.success({ code: "test-code" }); },
  request: options => { loginRequest = options; },
  getAccountInfoSync: () => ({ miniProgram: { envVersion: "release" } })
};
vm.runInNewContext(fs.readFileSync(require.resolve("../../miniprogram/core/api"), "utf8"), {
  module: isolated, wx: sandboxWx, require: () => ({ apiBaseUrl: "https://example.invalid" })
});
let failedLoginCallbacks = 0;
isolated.exports.listOrders(() => { failedLoginCallbacks++; });
assert.doesNotThrow(() => loginRequest.success({ statusCode: 200, data: null }));
assert.equal(failedLoginCallbacks, 1, "无效登录响应也必须结束加载");
isolated.exports.listOrders(() => { failedLoginCallbacks++; });
assert.equal(loginAttempts, 2, "失败后可以重新登录");
loginRequest.success({ statusCode: 200, data: { token: {} } });
assert.equal(store.apiSessionToken, undefined, "登录令牌必须是非空字符串");
assert.equal(failedLoginCallbacks, 2);
const pendingRequests = [];
sandboxWx.request = options => { pendingRequests.push(options); };
store.apiSessionToken = "expired";
isolated.exports.listOrders(() => {});
isolated.exports.listOrders(() => {});
const oldFirst = pendingRequests.shift();
const oldSecond = pendingRequests.shift();
oldFirst.success({ statusCode: 401, data: { error: "expired" } });
const renewedLogin = pendingRequests.shift();
renewedLogin.success({ statusCode: 200, data: { token: "renewed" } });
oldSecond.success({ statusCode: 401, data: { error: "expired" } });
assert.equal(loginAttempts, 3, "晚到的旧会话响应不能清除刚更新的令牌或重复登录");
assert.equal(store.apiSessionToken, "renewed");
assert.equal(pendingRequests.length, 2);
async function verifyAdminRecovery() {
  class Control {
    constructor(tag = "input") {
      this.tag = tag; this.children = []; this._value = ""; this.disabled = false;
    }
    set value(value) {
      this._value = this.tag === "select" && !this.children.some(item => item.value === value) ? "" : value;
    }
    get value() { return this._value; }
    append(...items) { this.children.push(...items); }
    appendChild(item) { this.append(item); }
    replaceChildren(...items) {
      this.children = items;
      if (this.tag === "select") this._value = items.length ? items[0].value : "";
    }
    addEventListener() {}
  }
  const controls = new Map();
  const document = {
    createElement: tag => new Control(tag),
    querySelectorAll: () => [],
    getElementById: id => {
      if (!controls.has(id)) controls.set(id, new Control(id === "schedule-expert" ? "select" : "input"));
      return controls.get(id);
    }
  };
  let timeout;
  let fetchOptions;
  const context = vm.createContext({
    document, window: { confirm: () => true }, AbortController,
    setTimeout: callback => { timeout = callback; return 1; }, clearTimeout: () => {},
    fetch: (url, options) => {
      fetchOptions = options;
      return new Promise((resolve, reject) => {
        if (options.signal) options.signal.addEventListener("abort", () => reject(new Error("aborted")));
      });
    }
  });
  vm.runInContext(fs.readFileSync(require.resolve("../../admin/ops-config.js"), "utf8"), context);
  vm.runInContext(`state.experts = [
    { id: "one", display_name: "甲", status: "online" },
    { id: "two", display_name: "乙", status: "offline" },
    { id: "hidden", display_name: "丙", status: "hidden" }
  ]; renderExperts();`, context);
  const select = document.getElementById("schedule-expert");
  select.value = "two";
  vm.runInContext("renderExperts()", context);
  assert.equal(select.value, "two", "专家列表刷新不能悄悄改变正在编辑的排班专家");
  vm.runInContext('editSchedule({ id: "old", expert_id: "hidden", starts_at: "", ends_at: "", status: "closed" })', context);
  assert.equal(select.value, "hidden", "隐藏专家的历史排班仍能编辑状态");
  document.getElementById("base").value = "https://example.invalid";
  const action = vm.runInContext('guarded(() => request("/api/ops/experts"))', context);
  const control = new Control("button");
  const completion = action({ currentTarget: control });
  assert.ok(fetchOptions.signal, "运营请求必须有超时取消信号");
  assert.equal(control.disabled, true);
  timeout();
  await completion;
  assert.equal(control.disabled, false, "超时后必须恢复操作按钮");
  assert.match(document.getElementById("status").textContent, /超时/);
}

verifyAdminRecovery().then(() => console.log(JSON.stringify({ validated: true }))).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
