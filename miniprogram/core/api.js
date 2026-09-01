var runtimeConfig = require("../config/runtime");
var TOKEN_KEY = "apiSessionToken";
var REQUEST_TIMEOUT_MS = 10000;
var loginCallbacks = null;

var REASON_MESSAGES = {
  "local-mode": "未配置线上服务地址，排盘和本地记录仍可使用",
  "invalid-base-url": "线上服务地址无效，请联系运营人员检查配置",
  "missing-login-code": "微信登录凭证获取失败，请稍后重试",
  "login-not-configured": "微信登录尚未配置，当前保留本地模式",
  "login-request-failed": "登录服务连接失败，请检查网络后重试",
  "wx-login-failed": "微信登录失败，请稍后重试",
  "request-failed": "网络连接失败，请检查网络后重试"
};

function userMessage(reason) {
  var value = String(reason || "").trim();
  return REASON_MESSAGES[value] || value || "请求未完成，请稍后重试";
}

function isRelease() {
  try {
    return wx.getAccountInfoSync().miniProgram.envVersion === "release";
  } catch (error) {
    return false;
  }
}

function normalizeBaseUrl(value) {
  var url = String(value || "").trim().replace(/\/+$/, "");
  if (!url) return { url: "", reason: "local-mode" };
  if (!/^https:\/\/[^/]+/i.test(url)) return { url: "", reason: "invalid-base-url" };
  return { url: url, reason: "" };
}

function environmentStatus() {
  var configured = runtimeConfig.apiBaseUrl;
  if (!isRelease()) configured = wx.getStorageSync("apiBaseUrl") || configured;
  var normalized = normalizeBaseUrl(configured);
  return { online: Boolean(normalized.url), baseUrl: normalized.url, reason: normalized.reason };
}

function baseUrl() {
  return environmentStatus().baseUrl;
}

function responseResult(ok, response, reason) {
  var reasonValue = reason || "";
  return {
    ok: Boolean(ok), statusCode: response ? response.statusCode : 0,
    data: response ? response.data : null, reason: reasonValue,
    message: ok ? "" : userMessage(reasonValue)
  };
}

function clearSession() { wx.removeStorageSync(TOKEN_KEY); }

function finishLogin(result) {
  var callbacks = loginCallbacks || [];
  loginCallbacks = null;
  callbacks.forEach(function (callback) { callback(result); });
}

function login(callback) {
  if (loginCallbacks) { loginCallbacks.push(callback); return; }
  loginCallbacks = [callback];
  var environment = environmentStatus();
  if (!environment.online) { finishLogin(responseResult(false, null, environment.reason)); return; }
  wx.login({
    success: function (loginResponse) {
      if (!loginResponse.code) { finishLogin(responseResult(false, null, "missing-login-code")); return; }
      wx.request({
        url: environment.baseUrl + "/api/auth/wechat", method: "POST", timeout: REQUEST_TIMEOUT_MS,
        data: { code: loginResponse.code }, header: { "content-type": "application/json" },
        success: function (response) {
          if (response.statusCode >= 200 && response.statusCode < 300 && response.data.token) {
            wx.setStorageSync(TOKEN_KEY, response.data.token);
            finishLogin(responseResult(true, response));
            return;
          }
          finishLogin(responseResult(false, response, response.data && response.data.error || "login-not-configured"));
        },
        fail: function (error) {
          finishLogin(Object.assign(responseResult(false, null, "login-request-failed"), { error: error }));
        }
      });
    },
    fail: function (error) {
      finishLogin(Object.assign(responseResult(false, null, "wx-login-failed"), { error: error }));
    }
  });
}

function request(path, options, callback, retried) {
  var environment = environmentStatus();
  var base = environment.baseUrl;
  if (!base) { callback(responseResult(false, null, environment.reason)); return; }
  var token = wx.getStorageSync(TOKEN_KEY);
  var headers = Object.assign({ "content-type": "application/json" }, options.header || {});
  if (token) headers.Authorization = "Bearer " + token;
  wx.request({
    url: base + path, method: options.method || "GET", data: options.data,
    header: headers, timeout: REQUEST_TIMEOUT_MS,
    success: function (response) {
      if (response.statusCode === 401 && !retried) {
        clearSession();
        login(function (loginResult) {
          if (loginResult.ok) request(path, options, callback, true);
          else callback(loginResult);
        });
        return;
      }
      callback(responseResult(response.statusCode >= 200 && response.statusCode < 300, response,
        response.data && response.data.error || ""));
    },
    fail: function (error) {
      callback(Object.assign(responseResult(false, null, "request-failed"), { error: error }));
    }
  });
}

function authenticatedRequest(path, options, callback) {
  var environment = environmentStatus();
  if (!environment.online) { callback(responseResult(false, null, environment.reason)); return; }
  if (wx.getStorageSync(TOKEN_KEY)) { request(path, options, callback, false); return; }
  login(function (loginResult) {
    if (!loginResult.ok) { callback(loginResult); return; }
    request(path, options, callback, false);
  });
}

function syncRecord(resource, payload, callback) {
  authenticatedRequest("/api/" + resource, { method: "POST", data: { payload: payload } }, function (response) {
    if (callback) callback({ synced: response.ok, response: response, reason: response.reason });
  });
}

function listRecords(resource, callback) {
  authenticatedRequest("/api/" + resource, {}, function (response) {
    callback({
      ok: response.ok,
      items: response.ok && response.data ? response.data.items || [] : [],
      reason: response.reason,
      message: response.message,
      response: response
    });
  });
}

function updateRecord(resource, id, status, callback) {
  authenticatedRequest("/api/" + resource + "/" + encodeURIComponent(id), { method: "PATCH", data: { status: status } }, callback);
}

function deleteRecord(resource, id, callback) {
  authenticatedRequest("/api/" + resource + "/" + encodeURIComponent(id), { method: "DELETE" }, callback);
}

function syncChart(payload, callback) { syncRecord("charts", payload, callback); }
function syncPrayer(payload, callback) { syncRecord("prayers", payload, callback); }
function syncWish(payload, callback) { syncRecord("wishes", payload, callback); }
function listPrayers(callback) { listRecords("prayers", callback); }
function listWishes(callback) { listRecords("wishes", callback); }
function updatePrayer(id, status, callback) { updateRecord("prayers", id, status, callback); }
function updateWish(id, status, callback) { updateRecord("wishes", id, status, callback); }
function deletePrayer(id, callback) { deleteRecord("prayers", id, callback); }
function deleteWish(id, callback) { deleteRecord("wishes", id, callback); }
function getConfig(callback) { request("/api/config", {}, callback); }
function listExperts(callback) { request("/api/experts", {}, callback); }
function listSchedules(expertId, callback) {
  var query = expertId ? "?expert_id=" + encodeURIComponent(expertId) : "";
  request("/api/schedules" + query, {}, callback);
}
function createOrder(payload, callback) {
  authenticatedRequest("/api/orders", { method: "POST", data: payload }, callback);
}
function prepareOrderPayment(orderId, callback) {
  authenticatedRequest("/api/orders/" + encodeURIComponent(orderId) + "/pay", { method: "POST", data: {} }, callback);
}
function getOrder(orderId, callback) {
  authenticatedRequest("/api/orders/" + encodeURIComponent(orderId), {}, callback);
}
function listOrders(callback) { authenticatedRequest("/api/orders", {}, callback); }

module.exports = {
  baseUrl: baseUrl, environmentStatus: environmentStatus, clearSession: clearSession,
  userMessage: userMessage,
  syncChart: syncChart, syncPrayer: syncPrayer, syncWish: syncWish,
  listPrayers: listPrayers, listWishes: listWishes,
  updatePrayer: updatePrayer, updateWish: updateWish,
  deletePrayer: deletePrayer, deleteWish: deleteWish,
  getConfig: getConfig, listExperts: listExperts, listSchedules: listSchedules,
  createOrder: createOrder, prepareOrderPayment: prepareOrderPayment,
  getOrder: getOrder, listOrders: listOrders
};
