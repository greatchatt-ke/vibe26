// 진입점: 초기화, 이벤트 바인딩, 화면 상태(보고 있는 날짜, 편집 중인 항목) 관리.

import * as store from './store.js';
import { addDays, formatKey, todayKey } from './date.js';
import { createView } from './view.js';

const $ = (id) => document.getElementById(id);

const els = {
  storageWarning: $('storage-warning'),
  prevDay: $('prev-day'),
  nextDay: $('next-day'),
  dateTitle: $('date-title'),
  todayChip: $('today-chip'),
  todayBtn: $('today-btn'),
  themeToggle: $('theme-toggle'),
  menuBtn: $('menu-btn'),
  carryBanner: $('carry-banner'),
  carryText: $('carry-text'),
  carryAccept: $('carry-accept'),
  carryDismiss: $('carry-dismiss'),
  progressBar: $('progress-bar'),
  progressFill: $('progress-fill'),
  progressText: $('progress-text'),
  addForm: $('add-form'),
  addInput: $('add-input'),
  pastNote: $('past-note'),
  filterButtons: [...document.querySelectorAll('[data-filter]')],
  list: $('todo-list'),
  empty: $('empty-state'),
  footer: $('footer'),
  remaining: $('remaining'),
  clearDone: $('clear-done'),
  toast: $('toast'),
  toastText: $('toast-text'),
  toastAction: $('toast-action'),
  menuDialog: $('menu-dialog'),
  shortcutsDialog: $('shortcuts-dialog'),
  backupFile: $('backup-file'),
};

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

let today = todayKey();
let viewDate = today;
let editingId = null;
let dragId = null;
let pendingFocus = null; // 다시 그린 뒤 포커스를 돌려줄 { id, selector }

store.init(today);
const view = createView(els);

/* ===== 렌더링 ===== */

function effectiveTheme() {
  const theme = store.getState().settings.theme;
  if (theme !== 'system') return theme;
  return darkQuery.matches ? 'dark' : 'light';
}

function applyTheme() {
  const theme = store.getState().settings.theme;
  if (theme === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

function render() {
  applyTheme();
  view.render({
    todos: store.todosFor(viewDate),
    filter: store.getState().settings.filter,
    viewDate,
    today,
    editingId,
    storageStatus: store.getStorageStatus(),
    carry: store.carryInfo(),
    theme: effectiveTheme(),
  });

  if (editingId) {
    const input = els.list.querySelector('.edit-input');
    if (input && document.activeElement !== input) {
      input.focus();
      input.select();
    }
  } else if (pendingFocus) {
    const li = els.list.querySelector(`li[data-id="${CSS.escape(pendingFocus.id)}"]`);
    li?.querySelector(pendingFocus.selector)?.focus();
  }
  pendingFocus = null;
}

store.subscribe(render);
darkQuery.addEventListener('change', render);

/* ===== 날짜 ===== */

// 페이지를 켜 둔 채 자정이 지나면 오늘을 다시 계산한다.
function checkDay() {
  const now = todayKey();
  if (now === today) return;
  if (viewDate === today) viewDate = now;
  today = now;
  editingId = null;
  store.checkDay(today);
  render();
}

function goTo(date) {
  viewDate = date > today ? today : date;
  editingId = null;
  render();
}

els.prevDay.addEventListener('click', () => goTo(addDays(viewDate, -1)));
els.nextDay.addEventListener('click', () => goTo(addDays(viewDate, 1)));
els.todayBtn.addEventListener('click', () => goTo(today));

setInterval(checkDay, 60_000);
window.addEventListener('focus', checkDay);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) checkDay();
});

/* ===== 토스트 ===== */

let toastTimer = null;
let toastCallback = null;

function showToast(message, actionLabel, onAction) {
  clearTimeout(toastTimer);
  els.toastText.textContent = message;
  toastCallback = onAction || null;
  els.toastAction.hidden = !onAction;
  els.toastAction.textContent = actionLabel || '';
  els.toast.classList.toggle('has-action', Boolean(onAction));
  els.toast.hidden = false;
  toastTimer = setTimeout(hideToast, 5000);
}

function hideToast() {
  clearTimeout(toastTimer);
  els.toast.hidden = true;
  toastCallback = null;
}

els.toastAction.addEventListener('click', () => {
  const callback = toastCallback;
  hideToast();
  callback?.();
});

/* ===== 추가 ===== */

els.addForm.addEventListener('submit', (e) => {
  e.preventDefault();
  checkDay();
  if (viewDate !== today) return;
  if (store.addTodo(els.addInput.value, today)) els.addInput.value = '';
  els.addInput.focus();
});

/* ===== 목록 조작 ===== */

function startEdit(id) {
  if (viewDate !== today) return;
  editingId = id;
  render();
}

function finishEdit(save, value) {
  const id = editingId;
  if (!id) return;
  editingId = null;
  pendingFocus = { id, selector: '[data-action="edit"]' };
  if (save) store.editTodo(id, value);
  render();
}

function removeTodo(id) {
  const removed = store.deleteTodo(id);
  if (!removed) return;
  showToast('할 일을 삭제했어요', '실행 취소', () => store.restoreTodo(removed));
}

const itemId = (target) => target.closest('li.todo')?.dataset.id;

els.list.addEventListener('click', (e) => {
  const id = itemId(e.target);
  const action = e.target.closest('[data-action]')?.dataset.action;
  if (!id || !action) return;
  if (action === 'important') {
    pendingFocus = { id, selector: '.star' };
    store.toggleImportant(id);
  } else if (action === 'edit') {
    startEdit(id);
  } else if (action === 'delete') {
    removeTodo(id);
  }
});

els.list.addEventListener('change', (e) => {
  if (!e.target.matches('.toggle')) return;
  const id = itemId(e.target);
  pendingFocus = { id, selector: '.toggle' };
  store.toggleTodo(id);
});

els.list.addEventListener('dblclick', (e) => {
  if (e.target.matches('.text')) startEdit(itemId(e.target));
});

els.list.addEventListener('keydown', (e) => {
  if (e.target.matches('.edit-input')) {
    if (e.isComposing) return; // 한글 조합 중 Enter는 무시
    if (e.key === 'Enter') {
      e.preventDefault();
      finishEdit(true, e.target.value);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      finishEdit(false);
    }
    return;
  }

  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && viewDate === today) {
    const li = e.target.closest('li.todo');
    if (!li) return;
    e.preventDefault();
    const down = e.key === 'ArrowDown';
    const sibling = down ? li.nextElementSibling : li.previousElementSibling;
    if (!sibling) return;
    pendingFocus = { id: li.dataset.id, selector: e.target.matches('.star') ? '.star' : '.toggle' };
    store.moveTodo(li.dataset.id, sibling.dataset.id, down);
  }
});

els.list.addEventListener('focusout', (e) => {
  if (e.target.matches('.edit-input') && editingId) finishEdit(true, e.target.value);
});

/* ===== 드래그 앤 드롭 ===== */

function clearDropMarks() {
  for (const li of els.list.querySelectorAll('.drop-before, .drop-after')) {
    li.classList.remove('drop-before', 'drop-after');
  }
}

function endDrag() {
  clearDropMarks();
  els.list.querySelector('.dragging')?.classList.remove('dragging');
  dragId = null;
}

els.list.addEventListener('dragstart', (e) => {
  const li = e.target.closest('li.todo');
  if (!li) return;
  dragId = li.dataset.id;
  li.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', dragId);
});

els.list.addEventListener('dragover', (e) => {
  if (!dragId) return;
  const li = e.target.closest('li.todo');
  clearDropMarks();
  if (!li || li.dataset.id === dragId) return;
  e.preventDefault();
  const rect = li.getBoundingClientRect();
  li.classList.add(e.clientY > rect.top + rect.height / 2 ? 'drop-after' : 'drop-before');
});

els.list.addEventListener('drop', (e) => {
  e.preventDefault();
  const li = e.target.closest('li.todo');
  if (dragId && li && li.dataset.id !== dragId) {
    store.moveTodo(dragId, li.dataset.id, li.classList.contains('drop-after'));
  }
  endDrag();
});

els.list.addEventListener('dragend', endDrag);

/* ===== 필터 · 테마 · 일괄 삭제 ===== */

for (const btn of els.filterButtons) {
  btn.addEventListener('click', () => store.setFilter(btn.dataset.filter));
}

els.themeToggle.addEventListener('click', () => {
  store.setTheme(effectiveTheme() === 'dark' ? 'light' : 'dark');
});

els.clearDone.addEventListener('click', () => {
  const count = store.todosFor(today).filter((t) => t.done).length;
  if (!count || !window.confirm(`완료한 항목 ${count}개를 지울까요?`)) return;
  store.clearDone(today);
  showToast(`완료 항목 ${count}개를 지웠어요`);
});

/* ===== 이월 ===== */

els.carryAccept.addEventListener('click', () => {
  const count = store.carryOver(today);
  if (count) showToast(`${count}개를 오늘로 가져왔어요`);
});

els.carryDismiss.addEventListener('click', () => store.dismissCarry());

/* ===== 메뉴 ===== */

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

async function exportMarkdown() {
  const todos = store.todosFor(viewDate);
  if (!todos.length) {
    showToast('복사할 할 일이 없어요');
    return;
  }
  const lines = [`# ${formatKey(viewDate)}`, '', ...todos.map((t) => `- [${t.done ? 'x' : ' '}] ${t.text}`)];
  const ok = await copyText(lines.join('\n'));
  showToast(ok ? 'Markdown으로 복사했어요' : '복사하지 못했어요');
}

function saveBackup() {
  const blob = new Blob([store.exportData()], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `todolist-backup-${today}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast('백업 파일을 저장했어요');
}

function cleanupOld() {
  const cutoff = addDays(today, -90);
  const count = store.countBefore(cutoff);
  if (!count) {
    showToast('90일 이전 기록이 없어요');
    return;
  }
  if (!window.confirm(`90일 이전 기록 ${count}개를 삭제할까요? 되돌릴 수 없어요.`)) return;
  store.deleteBefore(cutoff);
  if (viewDate < cutoff) viewDate = today;
  render();
  showToast(`기록 ${count}개를 삭제했어요`);
}

els.backupFile.addEventListener('change', async () => {
  const file = els.backupFile.files[0];
  els.backupFile.value = '';
  if (!file) return;
  const next = store.parseBackup(await file.text());
  if (!next) {
    window.alert('백업 파일 형식이 올바르지 않아요. 기존 데이터는 그대로예요.');
    return;
  }
  if (!window.confirm(`할 일 ${next.todos.length}개가 담긴 백업으로 현재 데이터를 덮어씁니다. 계속할까요?`)) return;
  viewDate = today;
  editingId = null;
  store.replaceState(next, today);
  showToast('백업을 복원했어요');
});

const MENU_ACTIONS = {
  'export-md': exportMarkdown,
  'backup-save': saveBackup,
  'backup-load': () => els.backupFile.click(),
  cleanup: cleanupOld,
  shortcuts: () => els.shortcutsDialog.showModal(),
};

els.menuBtn.addEventListener('click', () => els.menuDialog.showModal());

els.menuDialog.addEventListener('click', (e) => {
  const item = e.target.closest('[data-menu]');
  if (!item) return;
  els.menuDialog.close();
  MENU_ACTIONS[item.dataset.menu]();
});

// 바깥(배경) 클릭 시 닫기
for (const dialog of [els.menuDialog, els.shortcutsDialog]) {
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });
}

/* ===== 전역 단축키 ===== */

document.addEventListener('keydown', (e) => {
  if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
  const target = e.target;
  if (target.matches('input, textarea, select') || target.isContentEditable) return;
  if (document.querySelector('dialog[open]')) return;

  if (e.key === '?') {
    e.preventDefault();
    els.shortcutsDialog.showModal();
  } else if (e.key === '/' || e.code === 'KeyN') {
    e.preventDefault();
    if (viewDate !== today) goTo(today);
    els.addInput.focus();
  }
});

render();
