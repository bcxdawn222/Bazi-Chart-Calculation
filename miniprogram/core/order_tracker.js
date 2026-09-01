var STATUS_LABELS = {
  not_configured: "待配置",
  pending: "支付确认中",
  paid: "已支付"
};
var SERVICE_LABELS = {
  pending: "待确认",
  confirmed: "服务已确认",
  completed: "服务已完成",
  cancelled: "订单已取消"
};

function statusLabel(status) {
  return STATUS_LABELS[status] || "状态未知";
}

function serviceLabel(status) {
  return SERVICE_LABELS[status] || "服务状态未知";
}

function shouldPoll(order, attempt, maxAttempts) {
  return Boolean(order)
    && order.payment_status === "pending"
    && Number(attempt) < Number(maxAttempts);
}

function forView(order) {
  return Object.assign({}, order, {
    paymentLabel: statusLabel(order.payment_status),
    serviceLabel: serviceLabel(order.service_status),
    amountYuan: order.amount_cents == null ? "待配置" : (Number(order.amount_cents) / 100).toFixed(2)
  });
}

module.exports = {
  statusLabel: statusLabel, serviceLabel: serviceLabel,
  shouldPoll: shouldPoll, forView: forView
};
