import { api, clearSession, sessionBase, setSession } from './api.js';
import { el, errorBox, toast } from './ui.js';
import * as dashboard from './dashboard.js';
import * as config from './config.js';
import * as experts from './experts.js';
import * as schedules from './schedules.js';
import * as orders from './orders.js';

const ROUTES = {
  dashboard: { title: '概览', view: dashboard },
  config: { title: '运营开关', view: config },
  experts: { title: '专家管理', view: experts },
  schedules: { title: '排班管理', view: schedules },
  orders: { title: '订单管理', view: orders },
};

const $ = (id) => document.getElementById(id);
let renderToken = 0;

function showLogin() {
  $('app').hidden = true;
  $('login').hidden = false;
  $('login-token').value = '';
  $('login-token').focus();
}

async function navigate() {
  if ($('app').hidden) return;
  const name = location.hash.slice(1);
  const route = ROUTES[name] || ROUTES.dashboard;
  const routeName = ROUTES[name] ? name : 'dashboard';
  for (const link of document.querySelectorAll('.nav a')) {
    const active = link.dataset.route === routeName;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  }
  $('page-title').textContent = route.title;
  document.title = `${route.title} · 玄机运营后台`;

  // 每次导航用新的容器，旧视图的异步结果只会写进已脱离的节点
  const token = ++renderToken;
  const section = el('section');
  $('view').replaceChildren(el('div', { class: 'loading', text: '加载中…' }));
  try {
    await route.view.render(section);
    if (token === renderToken) $('view').replaceChildren(section);
  } catch (error) {
    if (token === renderToken) $('view').replaceChildren(errorBox(error.message));
  }
}

async function login(event) {
  event.preventDefault();
  const base = $('login-base').value.trim();
  const token = $('login-token').value;
  const errorNode = $('login-error');
  errorNode.textContent = '';
  if (!base || !token) { errorNode.textContent = '请填写接口地址和运营令牌'; return; }
  const submit = $('login-submit');
  submit.disabled = true;
  submit.textContent = '验证中…';
  setSession(base, token);
  try {
    // 用只读的专家列表校验令牌，同时确认接口可达
    await api.listExperts();
    $('session-host').textContent = sessionBase();
    $('login').hidden = true;
    $('app').hidden = false;
    $('login-token').value = '';
    await navigate();
  } catch (error) {
    clearSession();
    errorNode.textContent = error.message;
  } finally {
    submit.disabled = false;
    submit.textContent = '进入后台';
  }
}

function init() {
  if (/^https?:$/.test(location.protocol)) $('login-base').value = location.origin;
  $('insecure-hint').hidden = location.protocol === 'https:';
  $('login-form').addEventListener('submit', login);
  $('logout').addEventListener('click', () => { clearSession(); showLogin(); });
  window.addEventListener('hashchange', navigate);
  window.addEventListener('admin:unauthorized', () => {
    if ($('app').hidden) return;
    clearSession();
    showLogin();
    toast('运营令牌已失效，请重新登录', 'error');
  });
  $('login-token').focus();
}

init();
