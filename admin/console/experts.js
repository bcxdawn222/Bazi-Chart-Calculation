import { api, centsToYuan, EXPERT_LABELS, yuanToCents } from './api.js';
import { badge, busy, button, confirmDialog, el, field, formatTime, panel, select, table, toast } from './ui.js';

const STATUS_OPTIONS = Object.entries(EXPERT_LABELS);

export async function render(root) {
  const form = {
    id: '',
    name: el('input', { maxlength: '40', required: true }),
    price: el('input', { inputmode: 'decimal', placeholder: '例如 99 或 99.90' }),
    status: select(STATUS_OPTIONS, 'offline'),
    avatar: el('input', { type: 'url', maxlength: '500', placeholder: 'https://' }),
    bio: el('textarea', { maxlength: '500' }),
  };
  const formTitle = el('h3', { text: '新增专家' });
  const listSlot = el('div');

  const reset = () => {
    form.id = '';
    form.name.value = '';
    form.price.value = '';
    form.status.value = 'offline';
    form.avatar.value = '';
    form.bio.value = '';
    formTitle.textContent = '新增专家';
  };

  const edit = (expert) => {
    form.id = expert.id;
    form.name.value = expert.display_name || '';
    form.price.value = centsToYuan(expert.price_cents);
    form.status.value = expert.status;
    form.avatar.value = expert.avatar_url || '';
    form.bio.value = expert.bio || '';
    formTitle.textContent = `编辑：${expert.display_name}`;
    formTitle.scrollIntoView({ behavior: 'smooth', block: 'center' });
    form.name.focus();
  };

  const load = async () => {
    const experts = await api.listExperts();
    const rows = experts.map((expert) => el('tr', {},
      el('td', {}, el('strong', { text: expert.display_name }),
        expert.bio ? el('div', { class: 'muted small', text: expert.bio.slice(0, 40) }) : null),
      el('td', { class: 'num', text: expert.price_cents ? `¥${centsToYuan(expert.price_cents)}` : '未定价' }),
      el('td', {}, badge(expert.status, EXPERT_LABELS)),
      el('td', { class: 'num', text: formatTime(expert.updated_at) }),
      el('td', { class: 'actions' },
        button('编辑', () => edit(expert), 'btn-sm'),
        expert.status === 'online'
          ? button('下线', (event) => quickStatus(event, expert, 'offline'), 'btn-sm')
          : button('上线', (event) => quickStatus(event, expert, 'online'), 'btn-sm',
            { disabled: !expert.price_cents, title: expert.price_cents ? '' : '请先设置价格' }),
        button('删除', (event) => remove(event, expert), 'btn-sm btn-danger'))));
    listSlot.replaceChildren(table(
      [['专家'], ['价格', 'num'], ['状态'], ['更新时间', 'num'], ['操作']], rows, '还没有专家，先在上方新增'));
  };

  const quickStatus = async (event, expert, status) => {
    await busy(event.currentTarget, async () => {
      try {
        await api.saveExpert({ id: expert.id, status });
        toast(`${expert.display_name} 已${EXPERT_LABELS[status]}`);
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const remove = async (event, expert) => {
    const trigger = event.currentTarget;
    const ok = await confirmDialog(
      `确定删除「${expert.display_name}」吗？\n若已有排班或订单，将改为隐藏而不是删除。`, '删除');
    if (!ok) return;
    await busy(trigger, async () => {
      try {
        const result = await api.deleteExpert(expert.id);
        toast(result.status === 'hidden' ? '该专家有关联记录，已改为隐藏' : '已删除');
        if (form.id === expert.id) reset();
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const save = async (event) => {
    const name = form.name.value.trim();
    if (!name) { toast('请填写专家名称', 'error'); form.name.focus(); return; }
    let price;
    try { price = yuanToCents(form.price.value); } catch (error) { toast(error.message, 'error'); form.price.focus(); return; }
    if (form.status.value === 'online' && price === null) {
      toast('上线的专家必须设置价格', 'error');
      return;
    }
    await busy(event.currentTarget, async () => {
      try {
        await api.saveExpert({
          id: form.id, display_name: name, price_cents: price, status: form.status.value,
          avatar_url: form.avatar.value.trim(), bio: form.bio.value.trim(),
        });
        toast(form.id ? '专家已更新' : '专家已新增');
        reset();
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  root.append(
    el('section', { class: 'panel' },
      el('div', { class: 'panel-head' }, formTitle, el('p', { class: 'panel-note', text: '价格以元填写，保存为分' })),
      el('div', { class: 'form-grid' },
        field('专家名称', form.name), field('价格（元）', form.price), field('状态', form.status),
        field('头像地址', form.avatar), field('简介', form.bio, 'span-all')),
      el('div', { class: 'form-actions' },
        button('保存专家', save, 'btn-primary'), button('清空', reset, 'btn-ghost'))),
    panel('专家列表', '', listSlot));
  await load();
}
