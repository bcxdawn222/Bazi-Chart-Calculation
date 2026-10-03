import { api } from './api.js';
import { busy, button, confirmDialog, el, field, panel, toast } from './ui.js';

const SWITCHES = [
  {
    key: 'consultation', title: '真人咨询',
    desc: '关闭后小程序隐藏专家预约入口，已有订单不受影响。',
  },
  {
    key: 'payment', title: '微信支付',
    desc: '此处开启只是允许支付；服务器还需配置商户号与证书，两者都满足才会实际生效。',
  },
  {
    key: 'ai', title: 'AI 解读',
    desc: '需要服务器配置 AI 接入后才有实际效果。',
  },
];

function switchRow(item, info, refresh) {
  const enabled = Boolean(info && info.enabled);
  const reason = el('input', { value: (info && info.reason) || '', maxlength: '120', placeholder: '关闭时向用户展示的说明' });

  const setEnabled = (next) => async (event) => {
    const verb = next ? '开启' : '关闭';
    const trigger = event.currentTarget;
    if (!(await confirmDialog(`确定${verb}「${item.title}」吗？\n该变更会立即对小程序生效。`, verb))) return;
    await busy(trigger, async () => {
      try {
        // 线上旧版后端接受任意类型，这里必须发送真正的 JSON 布尔值
        await api.saveConfig(`${item.key}.enabled`, next === true);
        toast(`已${verb}${item.title}`);
        await refresh();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const saveReason = async (event) => {
    await busy(event.currentTarget, async () => {
      try {
        await api.saveConfig(`${item.key}.reason`, reason.value.trim());
        toast('说明已保存');
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  return el('div', { class: 'switch-row' },
    el('div', {},
      el('div', { class: 'switch-title' },
        el('span', { text: item.title }),
        el('span', { class: `badge ${enabled ? 'badge-ok' : 'badge-muted'}`, text: enabled ? '生效中' : '未生效' })),
      el('p', { class: 'switch-desc', text: item.desc }),
      el('div', { class: 'switch-reason' }, reason, button('保存说明', saveReason, 'btn-sm'))),
    el('div', { class: 'switch-actions' },
      button('开启', setEnabled(true), enabled ? 'btn-sm' : 'btn-primary btn-sm', { disabled: enabled }),
      button('关闭', setEnabled(false), 'btn-sm btn-danger', { disabled: !enabled && item.key !== 'payment' })));
}

function advancedEditor() {
  const key = el('input', { placeholder: '例如 consultation.channel', maxlength: '80' });
  const value = el('textarea', { placeholder: 'JSON 值，例如 true、"文本" 或 {"a":1}' });
  const isPublic = el('input', { type: 'checkbox', checked: true });

  const save = async (event) => {
    const name = key.value.trim();
    if (!name) { toast('请填写配置键', 'error'); return; }
    let parsed;
    try { parsed = JSON.parse(value.value); } catch { toast('配置值不是有效的 JSON', 'error'); return; }
    if (name.endsWith('.enabled') && typeof parsed !== 'boolean') {
      toast('开关配置只能是 true 或 false', 'error');
      return;
    }
    const trigger = event.currentTarget;
    if (!(await confirmDialog(`确定写入配置「${name}」吗？`, '写入'))) return;
    await busy(trigger, async () => {
      try {
        await api.saveConfig(name, parsed, isPublic.checked);
        toast('配置已写入');
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  return el('details', { class: 'advanced' },
    el('summary', { text: '高级：直接写入配置项' }),
    el('div', { class: 'form-grid' },
      field('配置键', key),
      field('配置值（JSON）', value, 'span-all'),
      el('label', { class: 'check span-all' }, isPublic, el('span', { text: '对小程序公开' }))),
    el('div', { class: 'form-actions' }, button('写入配置', save, 'btn-primary')));
}

export async function render(root) {
  const refresh = async () => {
    const config = await api.publicConfig();
    root.replaceChildren(
      panel('服务开关', '状态读取自小程序公开配置接口',
        ...SWITCHES.map((item) => switchRow(item, config[item.key], refresh))),
      panel('其他配置', '', advancedEditor()));
  };
  await refresh();
}
