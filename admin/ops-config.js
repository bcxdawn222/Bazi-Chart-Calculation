const $ = (id) => document.getElementById(id);
const base = () => $('base').value.trim().replace(/\/+$/, '');
const token = () => $('token').value;
const state = { experts: [], schedules: [], orders: [] };
const paymentLabels = { not_configured: '待配置', pending: '支付确认中', paid: '已支付' };
const serviceLabels = { pending: '待确认', confirmed: '服务已确认', completed: '服务已完成', cancelled: '订单已取消' };

function setStatus(value) { $('status').textContent = value; }

function toLocalInput(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || '').slice(0, 16);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function toIsoTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error('排班时间无效');
  return date.toISOString();
}

async function request(path, options = {}) {
  const endpoint = base();
  if (!/^https?:\/\/[^/]+/i.test(endpoint)) throw new Error('请先填写有效的接口地址');
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (path.startsWith('/api/ops/')) headers['X-Admin-Token'] = token();
  const response = await fetch(endpoint + path, { ...options, headers });
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch (error) { throw new Error(`接口返回了非 JSON 内容（${response.status}）`); }
  if (!response.ok) throw new Error(data.error || `请求失败：${response.status}`);
  return data;
}

function button(label, action, className = '') {
  const item = document.createElement('button');
  item.type = 'button';
  item.textContent = label;
  item.className = className;
  item.addEventListener('click', action);
  return item;
}

function record(title, meta, actions) {
  const root = document.createElement('div');
  root.className = 'record';
  const main = document.createElement('div');
  main.className = 'record-main';
  const heading = document.createElement('div');
  heading.className = 'record-title';
  heading.textContent = title;
  const detail = document.createElement('div');
  detail.className = 'record-meta';
  detail.textContent = meta;
  const controls = document.createElement('div');
  controls.className = 'record-actions';
  actions.forEach((item) => controls.appendChild(item));
  main.append(heading, detail);
  root.append(main, controls);
  return root;
}

function replaceRecords(rootId, records, emptyText) {
  const root = $(rootId);
  if (records.length) {
    root.replaceChildren(...records);
    return;
  }
  const empty = document.createElement('p');
  empty.className = 'empty';
  empty.textContent = emptyText;
  root.replaceChildren(empty);
}

async function readConfig() {
  const data = await request('/api/config');
  $('config').textContent = JSON.stringify(data, null, 2);
  setStatus('配置读取完成');
}

async function saveConfig() {
  let value;
  try { value = JSON.parse($('value').value); } catch (error) { throw new Error('配置值必须是合法 JSON'); }
  await request('/api/ops/config', {
    method: 'POST', body: JSON.stringify({ key: $('key').value.trim(), value, is_public: $('public').checked })
  });
  await readConfig();
  setStatus('配置保存完成');
}

function resetExpert() {
  $('expert-id').value = '';
  $('expert-name').value = '';
  $('expert-price').value = '';
  $('expert-bio').value = '';
  $('expert-avatar').value = '';
  $('expert-status').value = 'online';
}

function editExpert(item) {
  $('expert-id').value = item.id;
  $('expert-name').value = item.display_name;
  $('expert-price').value = item.price_cents == null ? '' : item.price_cents;
  $('expert-bio').value = item.bio;
  $('expert-avatar').value = item.avatar_url;
  $('expert-status').value = item.status;
}

function renderExperts() {
  replaceRecords('expert-list', state.experts.map((item) => record(
    item.display_name,
    `${item.status} · ${item.price_cents == null ? '未定价' : `${(item.price_cents / 100).toFixed(2)} 元`}`,
    [button('编辑', () => editExpert(item), 'secondary'),
      button('隐藏', guarded(() => confirmAction('确认隐藏该专家吗？', () => removeExpert(item.id))), 'danger')]
  )), '暂无专家');
  const select = $('schedule-expert');
  select.replaceChildren(...state.experts.filter((item) => item.status !== 'hidden').map((item) => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.display_name;
    return option;
  }));
}

async function loadExperts() {
  state.experts = (await request('/api/ops/experts')).items;
  renderExperts();
}

async function saveExpert() {
  const id = $('expert-id').value;
  const payload = {
    display_name: $('expert-name').value.trim(), bio: $('expert-bio').value.trim(),
    avatar_url: $('expert-avatar').value.trim(), status: $('expert-status').value,
    price_cents: $('expert-price').value === '' ? null : Number($('expert-price').value)
  };
  await request(id ? `/api/ops/experts/${id}` : '/api/ops/experts', {
    method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)
  });
  resetExpert();
  await loadExperts();
  setStatus('专家保存完成');
}

async function removeExpert(id) {
  await request(`/api/ops/experts/${id}`, { method: 'DELETE' });
  await loadExperts();
  setStatus('专家状态已更新');
}

function resetSchedule() {
  $('schedule-id').value = '';
  $('schedule-start').value = '';
  $('schedule-end').value = '';
  $('schedule-status').value = 'available';
}

function editSchedule(item) {
  $('schedule-id').value = item.id;
  $('schedule-expert').value = item.expert_id;
  $('schedule-start').value = toLocalInput(item.starts_at);
  $('schedule-end').value = toLocalInput(item.ends_at);
  $('schedule-status').value = item.status;
}

function renderSchedules() {
  const names = Object.fromEntries(state.experts.map((item) => [item.id, item.display_name]));
  replaceRecords('schedule-list', state.schedules.map((item) => record(
    names[item.expert_id] || item.expert_id,
    `${item.starts_at} 至 ${item.ends_at} · ${item.status}`,
    [button('编辑', () => editSchedule(item), 'secondary'),
      button('关闭', guarded(() => confirmAction('确认关闭该排班吗？', () => removeSchedule(item.id))), 'danger')]
  )), '暂无排班');
}

async function loadSchedules() {
  state.schedules = (await request('/api/ops/schedules')).items;
  renderSchedules();
}

async function saveSchedule() {
  const id = $('schedule-id').value;
  const payload = {
    expert_id: $('schedule-expert').value,
    starts_at: toIsoTime($('schedule-start').value),
    ends_at: toIsoTime($('schedule-end').value),
    status: $('schedule-status').value
  };
  await request(id ? `/api/ops/schedules/${id}` : '/api/ops/schedules', {
    method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)
  });
  resetSchedule();
  await loadSchedules();
  setStatus('排班保存完成');
}

async function removeSchedule(id) {
  await request(`/api/ops/schedules/${id}`, { method: 'DELETE' });
  await loadSchedules();
  setStatus('排班状态已更新');
}

async function updateService(item, status) {
  await request(`/api/ops/orders/${item.id}`, {
    method: 'PATCH', body: JSON.stringify({ service_status: status })
  });
  await loadOrders();
}

function renderOrders() {
  replaceRecords('order-list', state.orders.map((item) => record(
    item.subject,
    `${paymentLabels[item.payment_status] || item.payment_status} · ${serviceLabels[item.service_status] || item.service_status} · ${item.amount_cents == null ? '未定价' : `${(item.amount_cents / 100).toFixed(2)} 元`}`,
    item.service_status === 'pending'
      ? [item.payment_status === 'paid'
        ? button('确认服务', guarded(() => updateService(item, 'confirmed')), 'secondary')
        : item.payment_status === 'not_configured'
          ? button('取消订单', guarded(() => confirmAction('确认取消该未支付订单吗？', () => updateService(item, 'cancelled'))), 'danger')
          : null].filter(Boolean)
      : item.service_status === 'confirmed'
        ? [button('完成服务', guarded(() => updateService(item, 'completed')))]
        : []
  )), '暂无订单');
}

async function loadOrders() {
  state.orders = (await request('/api/ops/orders')).items;
  renderOrders();
  setStatus('订单读取完成');
}

function guarded(action) {
  return async (event) => {
    const control = event && event.currentTarget;
    if (control && control.disabled) return;
    if (control) control.disabled = true;
    try { await action(); } catch (error) { setStatus(error.message); } finally { if (control) control.disabled = false; }
  };
}

async function confirmAction(message, action) {
  if (!window.confirm(message)) return;
  await action();
}

document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab, .view-panel').forEach((item) => item.classList.remove('active'));
  tab.classList.add('active');
  $(tab.dataset.panel).classList.add('active');
}));

$('load').addEventListener('click', guarded(async () => { await Promise.all([readConfig(), loadExperts(), loadSchedules()]); }));
$('save').addEventListener('click', guarded(saveConfig));
$('clear').addEventListener('click', () => { $('token').value = ''; $('key').value = ''; $('value').value = ''; setStatus('已清空'); });
$('save-expert').addEventListener('click', guarded(saveExpert));
$('reset-expert').addEventListener('click', resetExpert);
$('save-schedule').addEventListener('click', guarded(saveSchedule));
$('reset-schedule').addEventListener('click', resetSchedule);
$('load-orders').addEventListener('click', guarded(loadOrders));
