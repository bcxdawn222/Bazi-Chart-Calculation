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

console.log(JSON.stringify({
  validated: page.data.experts.length === 1
    && page.data.availableSchedules.length === 1
    && page.data.availableSchedules[0].displayTime.includes("至")
    && paymentAttempts === 2
    && prepareAttempts === 2
    && page.data.orderStatus === "已支付"
    && page.data.paymentLoading === false,
}));
