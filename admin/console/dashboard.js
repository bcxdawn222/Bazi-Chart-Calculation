import { api, centsToYuan, PAYMENT_LABELS, SERVICE_LABELS } from './api.js';
import { badge, el, formatTime, panel, table } from './ui.js';

function stat(label, value, sub, tone = '') {
  return el('div', { class: `stat ${tone ? `stat-${tone}` : ''}`.trim() },
    el('span', { class: 'stat-label', text: label }),
    el('span', { class: 'stat-value', text: value }),
    sub ? el('span', { class: 'stat-sub', text: sub }) : null);
}

function serviceRow(name, info) {
  const enabled = Boolean(info && info.enabled);
  return el('tr', {},
    el('td', { text: name }),
    el('td', {}, el('span', { class: `badge ${enabled ? 'badge-ok' : 'badge-muted'}`, text: enabled ? '已开启' : '未开启' })),
    el('td', { class: 'muted', text: (info && info.reason) || '—' }));
}

export async function render(root) {
  const [experts, schedules, orders, config] = await Promise.allSettled([
    api.listExperts(), api.listSchedules(), api.listOrders(), api.publicConfig(),
  ]);
  const failed = [experts, schedules, orders, config].filter((item) => item.status === 'rejected');
  const value = (result) => (result.status === 'fulfilled' ? result.value : null);
  const expertList = value(experts);
  const scheduleList = value(schedules);
  const orderList = value(orders);
  const publicConfig = value(config);

  const now = Date.now();
  const online = expertList ? expertList.filter((item) => item.status === 'online').length : null;
  const openSlots = scheduleList
    ? scheduleList.filter((item) => item.status === 'available' && new Date(item.starts_at).getTime() > now).length
    : null;
  const awaiting = orderList
    ? orderList.filter((item) => item.kind !== 'analysis'
      && item.service_status === 'pending' && item.payment_status === 'paid').length
    : null;
  const paidOrders = orderList ? orderList.filter((item) => item.payment_status === 'paid') : null;
  const revenue = paidOrders ? paidOrders.reduce((sum, item) => sum + Number(item.amount_cents || 0), 0) : null;
  const show = (number) => (number === null ? '—' : String(number));

  root.append(el('div', { class: 'stats' },
    stat('在线专家', show(online), expertList ? `共 ${expertList.length} 位` : '读取失败', 'accent'),
    stat('可预约时段', show(openSlots), scheduleList ? `共 ${scheduleList.length} 个排班` : '读取失败'),
    stat('待确认服务', show(awaiting), '已支付、等待运营确认', awaiting ? 'warn' : ''),
    stat('已收款', revenue === null ? '—' : `¥${centsToYuan(revenue)}`,
      paidOrders ? `${paidOrders.length} 笔已支付订单` : '读取失败', 'gold')));

  if (failed.length) {
    root.append(el('div', { class: 'error-box', role: 'alert',
      text: `部分数据未能读取：${failed.map((item) => item.reason.message).join('；')}` }));
  }

  if (publicConfig) {
    root.append(panel('服务状态', '小程序端当前看到的开关状态',
      table([['服务'], ['状态'], ['说明']], [
        serviceRow('真人咨询', publicConfig.consultation),
        serviceRow('微信支付', publicConfig.payment),
        serviceRow('AI 解读', publicConfig.ai),
      ], '')));
  }

  if (orderList) {
    const recent = orderList.slice(0, 6).map((order) => el('tr', {},
      el('td', { class: 'mono', text: order.id }),
      el('td', { text: order.subject }),
      el('td', { class: 'num', text: `¥${centsToYuan(order.amount_cents) || '0.00'}` }),
      el('td', {}, badge(order.payment_status, PAYMENT_LABELS)),
      el('td', {}, badge(order.service_status, SERVICE_LABELS)),
      el('td', { class: 'num', text: formatTime(order.created_at) })));
    root.append(panel('最近订单', `共 ${orderList.length} 笔`,
      table([['订单号'], ['事项'], ['金额', 'num'], ['支付'], ['服务'], ['创建时间', 'num']], recent, '暂无订单')));
  }
}
