const REQUEST_TIMEOUT_MS = 10000;

export const PAYMENT_LABELS = { not_configured: '未发起支付', pending: '支付确认中', paid: '已支付' };
export const SERVICE_LABELS = { pending: '待确认', confirmed: '已确认', completed: '已完成', cancelled: '已取消' };
export const EXPERT_LABELS = { online: '在线', offline: '离线', hidden: '已隐藏' };
export const SCHEDULE_LABELS = { available: '可预约', booked: '已约满', closed: '已关闭' };

// 令牌只放内存，不写 localStorage / sessionStorage
const session = { base: '', token: '' };

export function setSession(base, token) {
  session.base = String(base || '').trim().replace(/\/+$/, '');
  session.token = String(token || '');
}

export function clearSession() {
  session.base = '';
  session.token = '';
}

export function sessionBase() { return session.base; }

async function request(path, options = {}) {
  if (!/^https?:\/\/[^/]+/i.test(session.base)) throw new Error('请先填写有效的接口地址');
  const headers = { 'Content-Type': 'application/json' };
  if (path.startsWith('/api/ops/')) headers['X-Admin-Token'] = session.token;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(session.base + path, {
      method: options.method || 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    const text = await response.text();
    let data = {};
    if (text) {
      try { data = JSON.parse(text); } catch { throw new Error(`接口返回了非 JSON 内容（${response.status}）`); }
    }
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('admin:unauthorized'));
      throw new Error(data.error || '运营令牌无效');
    }
    if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw new Error('请求超时，请检查网络后重试');
    if (error instanceof TypeError) throw new Error('无法连接接口，请检查地址或网络');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  publicConfig: () => request('/api/config'),
  saveConfig: (key, value, isPublic = true) =>
    request('/api/ops/config', { method: 'POST', body: { key, value, is_public: isPublic } }),

  listExperts: () => request('/api/ops/experts').then((data) => data.items || []),
  saveExpert: ({ id, ...fields }) => (id
    ? request(`/api/ops/experts/${encodeURIComponent(id)}`, { method: 'PUT', body: fields })
    : request('/api/ops/experts', { method: 'POST', body: fields })),
  deleteExpert: (id) => request(`/api/ops/experts/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  listSchedules: (expertId = '') =>
    request(`/api/ops/schedules${expertId ? `?expert_id=${encodeURIComponent(expertId)}` : ''}`)
      .then((data) => data.items || []),
  saveSchedule: ({ id, ...fields }) => (id
    ? request(`/api/ops/schedules/${encodeURIComponent(id)}`, { method: 'PUT', body: fields })
    : request('/api/ops/schedules', { method: 'POST', body: fields })),
  deleteSchedule: (id) => request(`/api/ops/schedules/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  listOrders: (paymentStatus = '', serviceStatus = '') => {
    const params = new URLSearchParams();
    if (paymentStatus) params.set('payment_status', paymentStatus);
    if (serviceStatus) params.set('service_status', serviceStatus);
    const query = params.toString();
    return request(`/api/ops/orders${query ? `?${query}` : ''}`).then((data) => data.items || []);
  },
  updateOrderStatus: (id, status) =>
    request(`/api/ops/orders/${encodeURIComponent(id)}`, { method: 'PATCH', body: { service_status: status } }),
};

// 元 → 分；空字符串表示不设置价格
export function yuanToCents(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error('价格须为正数，最多两位小数');
  const cents = Math.round(Number(text) * 100);
  if (!Number.isSafeInteger(cents) || cents <= 0) throw new Error('价格须大于 0');
  return cents;
}

export function centsToYuan(cents) {
  if (cents === null || cents === undefined || cents === '') return '';
  return (Number(cents) / 100).toFixed(2);
}

// 与 backend/order_store.py 的 SERVICE_TRANSITIONS 及附加条件保持一致
export function allowedTransitions(order) {
  // 详细解读支付后由系统自动交付，没有人工履约环节
  if (order.kind === 'analysis') {
    return order.service_status === 'pending' && order.payment_status === 'not_configured' ? ['cancelled'] : [];
  }
  const current = order.service_status;
  const paid = order.payment_status === 'paid';
  if (current === 'pending') {
    const next = [];
    if (paid) next.push('confirmed');
    if (order.payment_status === 'not_configured') next.push('cancelled');
    return next;
  }
  if (current === 'confirmed') return ['completed'];
  return [];
}
