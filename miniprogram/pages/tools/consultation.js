var api = require("../../core/api");
var orderTracker = require("../../core/order_tracker");

var initialData = {
  consultLoading: false,
  consultConfig: null,
  consultError: "",
  ordersMessage: "",
  experts: [],
  schedules: [],
  availableSchedules: [],
  selectedExpertId: "",
  selectedScheduleId: "",
  consultSubject: "排盘结果咨询",
  paymentLoading: false,
  currentOrderId: "",
  canRetryCurrentPayment: false,
  orderStatus: "",
  orders: []
};

function displayTime(value) {
  var date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || "");
  var pad = function (part) { return part < 10 ? "0" + part : String(part); };
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
    + " " + pad(date.getHours()) + ":" + pad(date.getMinutes());
}

function schedulesForExpert(schedules, expertId) {
  return schedules.filter(function (item) { return item.expert_id === expertId; });
}

function orderForView(order) {
  return Object.assign(orderTracker.forView(order), {
    canRetryPayment: order.payment_status !== "paid" && order.service_status === "pending"
  });
}

function stopPolling(page) {
  if (page.orderPollTimer) clearTimeout(page.orderPollTimer);
  page.orderPollTimer = null;
}

function applyConsultationData(page, responses, loadId) {
  if (page.consultDisposed || page.consultLoadId !== loadId) return;
  var configResponse = responses.config;
  if (!configResponse.ok) {
    page.setData({
      consultLoading: false,
      consultConfig: { unavailable: true, reason: configResponse.message },
      consultError: configResponse.message
    });
    return;
  }
  var expertResponse = responses.experts;
  var scheduleResponse = responses.schedules;
  var orderResponse = responses.orders;
  var experts = expertResponse.ok ? (expertResponse.data.items || []).filter(function (item) {
    return item.status === "online" && Number(item.price_cents) > 0;
  }) : [];
  var schedules = scheduleResponse.ok ? (scheduleResponse.data.items || []).map(function (item) {
    return Object.assign({}, item, {
      displayTime: displayTime(item.starts_at) + " 至 " + displayTime(item.ends_at)
    });
  }) : [];
  var errors = [];
  if (!expertResponse.ok) errors.push(expertResponse.message);
  if (!scheduleResponse.ok) errors.push(scheduleResponse.message);
  page.setData({
    consultLoading: false,
    consultConfig: configResponse.data,
    consultError: errors.join("；"),
    ordersMessage: orderResponse.ok ? "" : orderResponse.message,
    experts: experts,
    schedules: schedules,
    availableSchedules: schedulesForExpert(schedules, page.data.selectedExpertId),
    orders: orderResponse.ok ? (orderResponse.data.items || []).map(orderForView) : []
  });
}

function loadConsultationData() {
  var page = this;
  var loadId = (this.consultLoadId || 0) + 1;
  this.consultLoadId = loadId;
  this.consultDisposed = false;
  this.consultActive = true;
  this.setData({ consultLoading: true, consultError: "", ordersMessage: "" });
  var responses = {};
  var pending = 4;
  var done = function (key) {
    return function (response) {
      responses[key] = response;
      pending -= 1;
      if (!pending) applyConsultationData(page, responses, loadId);
    };
  };
  api.getConfig(done("config"));
  api.listExperts(done("experts"));
  api.listSchedules("", done("schedules"));
  api.listOrders(done("orders"));
}

function requestPayment(page, orderId, payment) {
  wx.requestPayment(Object.assign({}, payment, {
    success: function () {
      if (page.consultDisposed) return;
      page.setData({
        paymentLoading: false, currentOrderId: orderId,
        canRetryCurrentPayment: false, orderStatus: "支付结果确认中"
      });
      if (page.consultActive) page.pollOrder(orderId, 0);
    },
    fail: function (error) {
      if (page.consultDisposed) return;
      var cancelled = error && String(error.errMsg || "").indexOf("cancel") >= 0;
      page.setData({
        paymentLoading: false,
        currentOrderId: orderId,
        canRetryCurrentPayment: true,
        orderStatus: cancelled ? "支付已取消，可继续支付" : "支付未完成，可继续支付"
      });
      page.refreshOrders();
    }
  }));
}

function preparePayment(page, orderId) {
  if (page.data.paymentLoading) return;
  if (!page.consultActive) {
    page.setData({
      paymentLoading: false, currentOrderId: orderId, canRetryCurrentPayment: true,
      orderStatus: "支付已暂停，可返回页面继续支付"
    });
    return;
  }
  page.setData({
    paymentLoading: true, currentOrderId: orderId,
    canRetryCurrentPayment: false, orderStatus: "正在获取支付参数"
  });
  api.prepareOrderPayment(orderId, function (response) {
    if (page.consultDisposed) return;
    if (!page.consultActive) {
      page.setData({
        paymentLoading: false, canRetryCurrentPayment: true,
        orderStatus: "支付已暂停，可返回页面继续支付"
      });
      return;
    }
    if (!response.ok) {
      page.setData({ paymentLoading: false, canRetryCurrentPayment: true, orderStatus: response.message });
      return;
    }
    requestPayment(page, orderId, response.data.payment);
  });
}

var methods = {
  loadConsultationData: loadConsultationData,

  onConsultSubjectInput: function (event) { this.setData({ consultSubject: event.detail.value }); },

  selectExpert: function (event) {
    var expertId = event.currentTarget.dataset.id;
    this.setData({
      selectedExpertId: expertId,
      selectedScheduleId: "",
      availableSchedules: schedulesForExpert(this.data.schedules, expertId),
      orderStatus: ""
    });
  },

  selectSchedule: function (event) { this.setData({ selectedScheduleId: event.currentTarget.dataset.id }); },

  payConsultation: function () {
    if (this.data.paymentLoading) return;
    var page = this;
    var config = this.data.consultConfig || {};
    var expert = this.data.experts.find(function (item) { return item.id === page.data.selectedExpertId; });
    if (!config.consultation || !config.consultation.enabled) {
      wx.showToast({ title: "咨询入口暂未开放", icon: "none" }); return;
    }
    if (!config.payment || !config.payment.enabled) {
      wx.showToast({ title: config.payment && config.payment.reason || "支付暂未开放", icon: "none" }); return;
    }
    if (!expert) { wx.showToast({ title: "请选择在线专家", icon: "none" }); return; }
    if (!this.data.selectedScheduleId) { wx.showToast({ title: "请选择可预约时间", icon: "none" }); return; }
    if (!String(this.data.consultSubject || "").trim()) {
      wx.showToast({ title: "请填写咨询事项", icon: "none" }); return;
    }
    this.setData({ paymentLoading: true, canRetryCurrentPayment: false, orderStatus: "正在创建订单" });
    api.createOrder({
      subject: String(this.data.consultSubject).trim(), expert_id: expert.id,
      schedule_id: this.data.selectedScheduleId
    }, function (response) {
      if (page.consultDisposed) return;
      if (!response.ok) {
        page.setData({ paymentLoading: false, orderStatus: response.message });
        page.loadConsultationData();
        return;
      }
      var orderId = response.data.item.id;
      page.setData({ paymentLoading: false, currentOrderId: orderId });
      preparePayment(page, orderId);
    });
  },

  retryPayment: function (event) {
    var orderId = event && event.currentTarget.dataset.id || this.data.currentOrderId;
    if (!orderId || this.data.paymentLoading) return;
    preparePayment(this, orderId);
  },

  pollOrder: function (orderId, attempt) {
    var page = this;
    if (attempt === 0) stopPolling(this);
    api.getOrder(orderId, function (response) {
      if (page.consultDisposed || !page.consultActive) return;
      if (!response.ok) { page.setData({ orderStatus: response.message }); return; }
      var order = response.data.item;
      page.setData({ orderStatus: orderTracker.statusLabel(order.payment_status) });
      page.refreshOrders();
      if (!orderTracker.shouldPoll(order, attempt, 6)) {
        if (order.payment_status === "pending" && attempt >= 6) {
          page.setData({ orderStatus: "支付确认仍在处理中，可稍后手动刷新" });
        }
        return;
      }
      page.orderPollTimer = setTimeout(function () { page.pollOrder(orderId, attempt + 1); }, 1500);
    });
  },

  refreshOrders: function () {
    var page = this;
    api.listOrders(function (response) {
      if (page.consultDisposed) return;
      var orders = response.ok ? (response.data.items || []).map(orderForView) : page.data.orders;
      var current = orders.find(function (item) { return item.id === page.data.currentOrderId; });
      page.setData({
        ordersMessage: response.ok ? "" : response.message,
        orders: orders,
        canRetryCurrentPayment: current ? current.canRetryPayment : page.data.canRetryCurrentPayment,
        orderStatus: current && current.payment_status === "paid" ? "已支付" : page.data.orderStatus
      });
    });
  },

  onShow: function () {
    this.consultActive = true;
    if (this.consultWasHidden && this.data.mode === "consult") {
      this.consultWasHidden = false;
      this.loadConsultationData();
    }
  },
  onHide: function () {
    this.consultActive = false;
    this.consultWasHidden = true;
    stopPolling(this);
  },
  onUnload: function () {
    this.consultDisposed = true;
    this.consultActive = false;
    stopPolling(this);
  }
};

module.exports = { initialData: initialData, methods: methods };
