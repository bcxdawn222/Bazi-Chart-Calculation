import { allowedTransitions, api, centsToYuan, PAYMENT_LABELS, SERVICE_LABELS } from './api.js';
import { badge, busy, button, confirmDialog, el, field, formatTime, panel, select, table, toast } from './ui.js';

const ACTIONS = {
  confirmed: { label: '确认服务', variant: 'btn-primary', prompt: '确认已与用户约定服务？' },
  completed: { label: '标记完成', variant: '', prompt: '确认该咨询服务已完成？完成后用户可评价。' },
  cancelled: { label: '取消订单', variant: 'btn-danger', prompt: '确定取消该订单？此操作不可撤销。' },
};

export async function render(root) {
  const experts = await api.listExperts().catch(() => []);
  const nameOf = new Map(experts.map((item) => [item.id, item.display_name]));
  const paymentFilter = select([['', '全部'], ...Object.entries(PAYMENT_LABELS)]);
  const serviceFilter = select([['', '全部'], ...Object.entries(SERVICE_LABELS)]);
  const summary = el('p', { class: 'panel-note' });
  const listSlot = el('div');

  const changeStatus = async (event, order, next) => {
    const action = ACTIONS[next];
    const trigger = event.currentTarget;
    if (!(await confirmDialog(`${action.prompt}\n订单：${order.id}`, action.label))) return;
    await busy(trigger, async () => {
      try {
        await api.updateOrderStatus(order.id, next);
        toast(`订单已${SERVICE_LABELS[next]}`);
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const load = async () => {
    const orders = await api.listOrders(paymentFilter.value, serviceFilter.value);
    const total = orders
      .filter((item) => item.payment_status === 'paid')
      .reduce((sum, item) => sum + Number(item.amount_cents || 0), 0);
    summary.textContent = `共 ${orders.length} 笔，其中已收款 ¥${centsToYuan(total) || '0.00'}（最多显示 500 笔）`;
    const rows = orders.map((order) => {
      const next = allowedTransitions(order);
      const analysis = order.kind === 'analysis';
      const locked = order.service_status === 'pending' && order.payment_status === 'pending';
      return el('tr', {},
        el('td', { class: 'mono', text: order.id, title: order.transaction_id ? `微信交易号 ${order.transaction_id}` : '' }),
        el('td', {}, el('div', { text: order.subject }),
          analysis ? el('span', { class: 'muted small', text: '详细解读' }) : null),
        el('td', { text: order.expert_id ? (nameOf.get(order.expert_id) || order.expert_id) : '—' }),
        el('td', { class: 'num', text: order.amount_cents ? `¥${centsToYuan(order.amount_cents)}` : '—' }),
        el('td', {}, badge(order.payment_status, PAYMENT_LABELS)),
        el('td', {}, badge(order.service_status, SERVICE_LABELS)),
        el('td', { class: 'num', text: formatTime(order.created_at) }),
        el('td', { class: 'actions' },
          next.length
            ? next.map((status) => button(ACTIONS[status].label, (event) => changeStatus(event, order, status),
              `btn-sm ${ACTIONS[status].variant}`))
            : el('span', { class: 'muted small', text: locked ? '等待支付结果' : analysis ? '自动交付' : '—' })));
    });
    listSlot.replaceChildren(table(
      [['订单号'], ['事项'], ['专家'], ['金额', 'num'], ['支付'], ['服务'], ['创建时间', 'num'], ['操作']],
      rows, '没有符合条件的订单'));
  };

  const reload = () => load().catch((error) => toast(error.message, 'error'));
  paymentFilter.addEventListener('change', reload);
  serviceFilter.addEventListener('change', reload);

  root.append(panel('订单', '',
    el('div', { class: 'toolbar' },
      field('支付状态', paymentFilter), field('服务状态', serviceFilter),
      button('刷新', (event) => busy(event.currentTarget, load).catch((error) => toast(error.message, 'error')))),
    summary,
    listSlot,
    el('p', { class: 'hint',
      text: '已发起支付的订单不能在这里直接取消，请先在微信支付商户平台核实交易并完成退款。' })));
  await load();
}
