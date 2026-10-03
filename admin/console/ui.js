// 所有文本一律走 textContent，不拼接 innerHTML
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    // textarea 没有 value 特性，统一按属性赋值
    else if (key === 'value') node.value = String(value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key in node && typeof value !== 'string') node[key] = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function toast(message, type = 'ok') {
  const root = document.getElementById('toasts');
  const item = el('div', { class: `toast toast-${type}`, role: type === 'error' ? 'alert' : 'status', text: message });
  root.append(item);
  setTimeout(() => item.remove(), type === 'error' ? 6000 : 3200);
}

export function confirmDialog(message, okText = '确定') {
  const dialog = document.getElementById('confirm');
  document.getElementById('confirm-message').textContent = message;
  document.getElementById('confirm-ok').textContent = okText;
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'ok'), { once: true });
  });
}

export function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function toLocalInput(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function fromLocalInput(value) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) throw new Error('请填写有效的时间');
  return date.toISOString();
}

const TONES = {
  online: 'ok', available: 'ok', paid: 'ok', completed: 'ok', confirmed: 'gold',
  pending: 'warn', offline: 'muted', booked: 'gold', closed: 'muted',
  hidden: 'muted', cancelled: 'danger', not_configured: 'muted',
};

export function badge(status, labels) {
  return el('span', { class: `badge badge-${TONES[status] || 'muted'}`, text: labels[status] || status || '—' });
}

export function button(label, onclick, variant = '', extra = {}) {
  return el('button', { type: 'button', class: `btn ${variant}`.trim(), text: label, onclick, ...extra });
}

// 执行期间禁用按钮，防止重复提交
export async function busy(btn, task) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = '处理中…';
  try {
    return await task();
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

export function field(label, input, extraClass = '') {
  return el('label', { class: `field ${extraClass}`.trim() }, el('span', { class: 'field-label', text: label }), input);
}

export function select(options, value = '') {
  const node = el('select');
  for (const [optionValue, optionLabel] of options) {
    node.append(el('option', { value: optionValue, text: optionLabel, selected: optionValue === value }));
  }
  return node;
}

export function table(headers, rows, emptyText) {
  const head = el('thead', {}, el('tr', {}, headers.map(([text, cls]) => el('th', { class: cls, text }))));
  const body = el('tbody');
  if (!rows.length) {
    body.append(el('tr', {}, el('td', { class: 'empty', colspan: String(headers.length), text: emptyText })));
  } else {
    body.append(...rows);
  }
  return el('div', { class: 'table-wrap' }, el('table', { class: 'table' }, head, body));
}

export function panel(title, note, ...content) {
  return el('section', { class: 'panel' },
    el('div', { class: 'panel-head' }, el('h3', { text: title }), note ? el('p', { class: 'panel-note', text: note }) : null),
    ...content);
}

export function errorBox(message) {
  return el('div', { class: 'error-box', role: 'alert', text: message });
}
