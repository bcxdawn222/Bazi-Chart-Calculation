var STATUS_LABELS = {
  not_configured: "待配置",
  pending: "支付确认中",
  paid: "已支付"
};

function statusLabel(status) {
  return STATUS_LABELS[status] || "状态未知";
}

function shouldPoll(order, attempt, maxAttempts) {
  return Boolean(order)
    && order.payment_status === "pending"
    && Number(attempt) < Number(maxAttempts);
}

function forView(order) {
  return Object.assign({}, order, {
    paymentLabel: statusLabel(order.payment_status),
    amountYuan: order.amount_cents == null ? "待配置" : (Number(order.amount_cents) / 100).toFixed(2)
  });
}

module.exports = { statusLabel: statusLabel, shouldPoll: shouldPoll, forView: forView };
