// DOM 렌더링. 사용자 입력은 항상 textContent로만 넣는다 (innerHTML 미사용).

import { addDays, formatKey, shortLabel } from './date.js';

const FILTER_EMPTY = {
  active: '진행 중인 할 일이 없어요',
  done: '완료한 할 일이 없어요',
};

const STORAGE_MESSAGES = {
  unavailable: '이 브라우저에서는 저장되지 않습니다. 페이지를 닫으면 내용이 사라져요.',
  quota: '저장 공간이 부족합니다. 백업 후 오래된 기록을 정리하세요.',
};

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (key in el) el[key] = value;
    else el.setAttribute(key, value === true ? '' : value);
  }
  el.append(...children);
  return el;
}

function renderItem(todo, editable, editing) {
  const li = h('li', {
    class: `todo${todo.done ? ' done' : ''}${todo.important ? ' important' : ''}`,
    'data-id': todo.id,
    draggable: editable && !editing,
  });

  const star = editable
    ? h('button', {
        type: 'button',
        class: 'star',
        'data-action': 'important',
        'aria-pressed': String(todo.important),
        'aria-label': todo.important ? '중요 표시 해제' : '중요 표시',
        title: '중요',
        text: '★',
      })
    : h('span', { class: 'star static', 'aria-hidden': 'true', text: todo.important ? '★' : '' });

  const toggle = h('input', {
    type: 'checkbox',
    class: 'toggle',
    checked: todo.done,
    'aria-label': `${todo.text} 완료`,
  });

  const body = editing
    ? h('input', { type: 'text', class: 'edit-input', value: todo.text, maxLength: 200, 'aria-label': '할 일 수정' })
    : h('span', { class: 'text', text: todo.text });
  const content = h('div', { class: 'content' }, body);
  if (todo.carriedFrom) {
    content.append(h('span', { class: 'badge', title: `${shortLabel(todo.carriedFrom)}에서 이월`, text: '이월' }));
  }

  li.append(star, toggle, content);

  if (editable && !editing) {
    li.append(h('div', { class: 'actions' },
      h('button', { type: 'button', class: 'icon-btn small', 'data-action': 'edit', 'aria-label': `${todo.text} 수정`, title: '수정', text: '✎' }),
      h('button', { type: 'button', class: 'icon-btn small danger', 'data-action': 'delete', 'aria-label': `${todo.text} 삭제`, title: '삭제', text: '✕' }),
    ));
  }
  return li;
}

export function createView(els) {
  function renderStorage(status) {
    const message = STORAGE_MESSAGES[status];
    els.storageWarning.hidden = !message;
    if (message) els.storageWarning.textContent = message;
  }

  function renderCarry(carry, isToday, today) {
    els.carryBanner.hidden = !(carry && isToday);
    if (!carry) return;
    const when = carry.date === addDays(today, -1) ? '어제' : shortLabel(carry.date);
    els.carryText.textContent = `${when} 못 끝낸 ${carry.count}개를 오늘로 가져올까요?`;
  }

  function renderProgress(total, done, isToday) {
    const pct = total ? Math.round((done / total) * 100) : 0;
    els.progressFill.style.width = `${pct}%`;
    els.progressBar.setAttribute('aria-valuenow', String(pct));
    els.progressBar.classList.toggle('complete', total > 0 && done === total);
    if (total === 0) els.progressText.textContent = '아직 할 일이 없어요';
    else if (done === total) els.progressText.textContent = `${done} / ${total} 완료 · ${isToday ? '오늘' : '이날'} 할 일을 모두 끝냈어요 🎉`;
    else els.progressText.textContent = `${done} / ${total} 완료 (${pct}%)`;
  }

  function render({ todos, filter, viewDate, today, editingId, storageStatus, carry, theme }) {
    const isToday = viewDate === today;
    const total = todos.length;
    const done = todos.filter((t) => t.done).length;

    els.dateTitle.textContent = formatKey(viewDate);
    els.todayChip.hidden = !isToday;
    els.todayBtn.hidden = isToday;
    els.nextDay.disabled = isToday;

    const dark = theme === 'dark';
    els.themeToggle.textContent = dark ? '☀' : '☾';
    els.themeToggle.setAttribute('aria-label', dark ? '라이트 모드로 전환' : '다크 모드로 전환');

    renderStorage(storageStatus);
    renderCarry(carry, isToday, today);
    renderProgress(total, done, isToday);

    els.addForm.hidden = !isToday;
    els.pastNote.hidden = isToday;

    for (const btn of els.filterButtons) {
      const active = btn.dataset.filter === filter;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', String(active));
    }

    const visible = todos.filter((t) => filter === 'all' || (filter === 'done' ? t.done : !t.done));
    els.list.replaceChildren(...visible.map((t) => renderItem(t, isToday, t.id === editingId)));

    let empty = '';
    if (total === 0) empty = isToday ? '오늘 할 일을 추가해 보세요' : '이 날에는 할 일이 없어요';
    else if (visible.length === 0) empty = FILTER_EMPTY[filter];
    els.empty.hidden = !empty;
    els.empty.textContent = empty;

    els.footer.hidden = !(isToday && total > 0);
    els.remaining.textContent = `남은 할 일 ${total - done}개`;
    els.clearDone.disabled = done === 0;
  }

  return { render };
}
