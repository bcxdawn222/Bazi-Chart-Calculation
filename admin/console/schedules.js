import { api, EXPERT_LABELS, SCHEDULE_LABELS } from './api.js';
import {
  badge, busy, button, confirmDialog, el, field, formatTime, fromLocalInput, panel, select, table, toast, toLocalInput,
} from './ui.js';

const STATUS_OPTIONS = Object.entries(SCHEDULE_LABELS);

function addMinutes(localValue, minutes) {
  const date = new Date(localValue);
  if (Number.isNaN(date.getTime())) return '';
  return toLocalInput(new Date(date.getTime() + minutes * 60000).toISOString());
}

export async function render(root) {
  const experts = await api.listExperts();
  const nameOf = new Map(experts.map((item) => [item.id, item.display_name]));
  // 隐藏专家也列出来，历史排班才能正常显示和编辑
  const expertOptions = experts.map((item) => [item.id,
    item.status === 'online' ? item.display_name : `${item.display_name}（${EXPERT_LABELS[item.status]}）`]);

  const filter = select([['', '全部专家'], ...expertOptions]);
  const form = {
    id: '',
    expert: select([['', '请选择专家'], ...expertOptions]),
    start: el('input', { type: 'datetime-local' }),
    end: el('input', { type: 'datetime-local' }),
    status: select(STATUS_OPTIONS, 'available'),
  };
  const formTitle = el('h3', { text: '新增排班' });
  const listSlot = el('div');

  const reset = () => {
    form.id = '';
    form.expert.value = filter.value;
    form.start.value = '';
    form.end.value = '';
    form.status.value = 'available';
    formTitle.textContent = '新增排班';
  };

  const edit = (schedule) => {
    form.id = schedule.id;
    form.expert.value = schedule.expert_id;
    form.start.value = toLocalInput(schedule.starts_at);
    form.end.value = toLocalInput(schedule.ends_at);
    form.status.value = schedule.status;
    formTitle.textContent = '编辑排班';
    formTitle.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const load = async () => {
    const schedules = await api.listSchedules(filter.value);
    const now = Date.now();
    const rows = schedules.map((schedule) => {
      const past = new Date(schedule.starts_at).getTime() <= now;
      return el('tr', {},
        el('td', { text: nameOf.get(schedule.expert_id) || schedule.expert_id }),
        el('td', { class: 'num', text: formatTime(schedule.starts_at) }),
        el('td', { class: 'num', text: formatTime(schedule.ends_at) }),
        el('td', {}, badge(schedule.status, SCHEDULE_LABELS),
          past ? el('span', { class: 'muted small', text: ' 已过期' }) : null),
        el('td', { class: 'actions' },
          button('编辑', () => edit(schedule), 'btn-sm'),
          button('删除', (event) => remove(event, schedule), 'btn-sm btn-danger')));
    });
    listSlot.replaceChildren(table(
      [['专家'], ['开始', 'num'], ['结束', 'num'], ['状态'], ['操作']], rows, '没有排班'));
  };

  const remove = async (event, schedule) => {
    const trigger = event.currentTarget;
    const ok = await confirmDialog(
      `确定删除 ${formatTime(schedule.starts_at)} 的排班吗？\n若已有订单，将改为关闭而不是删除。`, '删除');
    if (!ok) return;
    await busy(trigger, async () => {
      try {
        const result = await api.deleteSchedule(schedule.id);
        toast(result.status === 'closed' ? '该排班已有订单，已改为关闭' : '已删除');
        if (form.id === schedule.id) reset();
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const save = async (event) => {
    if (!form.expert.value) { toast('请选择专家', 'error'); return; }
    let startsAt;
    let endsAt;
    try {
      startsAt = fromLocalInput(form.start.value);
      endsAt = fromLocalInput(form.end.value);
    } catch (error) { toast(error.message, 'error'); return; }
    if (new Date(endsAt) <= new Date(startsAt)) { toast('结束时间必须晚于开始时间', 'error'); return; }
    if (form.status.value === 'available' && new Date(startsAt).getTime() <= Date.now()) {
      toast('开放预约的排班必须在未来', 'error');
      return;
    }
    await busy(event.currentTarget, async () => {
      try {
        await api.saveSchedule({
          id: form.id, expert_id: form.expert.value, starts_at: startsAt, ends_at: endsAt, status: form.status.value,
        });
        toast(form.id ? '排班已更新' : '排班已新增');
        reset();
        await load();
      } catch (error) { toast(error.message, 'error'); }
    });
  };

  const duration = (minutes) => () => {
    if (!form.start.value) { toast('请先选择开始时间', 'error'); return; }
    form.end.value = addMinutes(form.start.value, minutes);
  };

  filter.addEventListener('change', () => { reset(); load().catch((error) => toast(error.message, 'error')); });

  root.append(
    el('section', { class: 'panel' },
      el('div', { class: 'panel-head' }, formTitle,
        el('p', { class: 'panel-note', text: '已有订单的排班不能修改专家或时间' })),
      el('div', { class: 'form-grid' },
        field('专家', form.expert), field('开始时间', form.start), field('结束时间', form.end), field('状态', form.status)),
      el('div', { class: 'form-actions' },
        button('保存排班', save, 'btn-primary'),
        button('时长 30 分钟', duration(30), 'btn-ghost'),
        button('时长 60 分钟', duration(60), 'btn-ghost'),
        button('清空', reset, 'btn-ghost'))),
    panel('排班列表', '', el('div', { class: 'toolbar' }, field('按专家筛选', filter)), listSlot));
  if (!experts.length) toast('还没有专家，请先到「专家」页新增', 'error');
  await load();
}
