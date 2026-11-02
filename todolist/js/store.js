// 상태 관리 + localStorage 입출력.
// 모든 변경은 commit()을 거쳐 저장 → 구독자 알림 순서로 처리한다.

import { DATE_RE } from './date.js';

const STORAGE_KEY = 'todolist:v1';
const BACKUP_KEY = 'todolist:backup';
export const MAX_LENGTH = 200;
const FILTERS = ['all', 'active', 'done'];
const THEMES = ['system', 'light', 'dark'];

const listeners = new Set();
let state;
let storageStatus = 'ok'; // 'ok' | 'unavailable' | 'quota'

const isDateKey = (v) => typeof v === 'string' && DATE_RE.test(v);

function newId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function defaultState(today) {
  return {
    version: 1,
    todos: [],
    settings: { filter: 'all', theme: 'system' },
    lastOpenedDate: today,
    carryPrompt: null,
  };
}

// 저장된 값이나 백업 파일을 검증해 안전한 형태로 바꾼다. 형식이 틀리면 null.
function normalizeState(obj) {
  if (!obj || typeof obj !== 'object' || obj.version !== 1 || !Array.isArray(obj.todos)) return null;
  const todos = [];
  for (const t of obj.todos) {
    if (!t || typeof t.id !== 'string' || typeof t.text !== 'string' || !isDateKey(t.date)) return null;
    const todo = {
      id: t.id,
      text: t.text.slice(0, MAX_LENGTH),
      done: Boolean(t.done),
      important: Boolean(t.important),
      date: t.date,
      order: Number.isFinite(t.order) ? t.order : 0,
      createdAt: Number.isFinite(t.createdAt) ? t.createdAt : Date.now(),
    };
    if (isDateKey(t.carriedFrom)) todo.carriedFrom = t.carriedFrom;
    if (todo.done && Number.isFinite(t.completedAt)) todo.completedAt = t.completedAt;
    todos.push(todo);
  }
  const settings = obj.settings || {};
  return {
    version: 1,
    todos,
    settings: {
      filter: FILTERS.includes(settings.filter) ? settings.filter : 'all',
      theme: THEMES.includes(settings.theme) ? settings.theme : 'system',
    },
    lastOpenedDate: isDateKey(obj.lastOpenedDate) ? obj.lastOpenedDate : null,
    carryPrompt: isDateKey(obj.carryPrompt) ? obj.carryPrompt : null,
  };
}

function parse(raw) {
  try {
    return normalizeState(JSON.parse(raw));
  } catch {
    return null;
  }
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    storageStatus = 'ok';
  } catch (e) {
    storageStatus = e && e.name === 'QuotaExceededError' ? 'quota' : 'unavailable';
  }
}

function emit() {
  for (const fn of listeners) fn();
}

function commit(mutate) {
  mutate(state);
  persist();
  emit();
}

// 날짜가 바뀌었으면 마지막으로 연 날의 미완료 항목을 이월 후보로 표시한다.
function rollover(today) {
  const last = state.lastOpenedDate;
  if (last && last < today) {
    const hasUndone = state.todos.some((t) => t.date === last && !t.done);
    state.carryPrompt = hasUndone ? last : null;
  }
  state.lastOpenedDate = today;
}

function nextOrder(date) {
  let max = -1;
  for (const t of state.todos) if (t.date === date && t.order > max) max = t.order;
  return max + 1;
}

const find = (id) => state.todos.find((t) => t.id === id);

/* ===== 초기화 / 조회 ===== */

export function init(today) {
  let raw = null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    storageStatus = 'unavailable';
  }
  state = defaultState(today);
  if (raw) {
    const parsed = parse(raw);
    if (parsed) {
      state = parsed;
    } else {
      // 읽을 수 없는 데이터는 지우지 않고 따로 보존
      try { localStorage.setItem(BACKUP_KEY, raw); } catch {}
    }
  }
  rollover(today);
  persist();
}

export const getState = () => state;
export const getStorageStatus = () => storageStatus;

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// 중요 항목을 위로, 그 안에서는 사용자가 정한 순서대로
export function todosFor(date) {
  return state.todos
    .filter((t) => t.date === date)
    .sort((a, b) => (b.important - a.important) || (a.order - b.order) || (a.createdAt - b.createdAt));
}

export function carryInfo() {
  const date = state.carryPrompt;
  if (!date) return null;
  const count = state.todos.filter((t) => t.date === date && !t.done).length;
  return count ? { date, count } : null;
}

export function checkDay(today) {
  if (state.lastOpenedDate === today) return;
  commit(() => rollover(today));
}

/* ===== 할 일 조작 ===== */

export function addTodo(text, date) {
  const value = text.trim().slice(0, MAX_LENGTH);
  if (!value) return false;
  commit((s) => {
    s.todos.push({
      id: newId(),
      text: value,
      done: false,
      important: false,
      date,
      order: nextOrder(date),
      createdAt: Date.now(),
    });
  });
  return true;
}

export function toggleTodo(id) {
  const todo = find(id);
  if (!todo) return;
  commit(() => {
    todo.done = !todo.done;
    if (todo.done) todo.completedAt = Date.now();
    else delete todo.completedAt;
  });
}

export function editTodo(id, text) {
  const todo = find(id);
  const value = text.trim().slice(0, MAX_LENGTH);
  if (!todo || !value || value === todo.text) return;
  commit(() => { todo.text = value; });
}

export function deleteTodo(id) {
  const todo = find(id);
  if (!todo) return null;
  commit((s) => { s.todos = s.todos.filter((t) => t.id !== id); });
  return todo;
}

export function restoreTodo(todo) {
  if (find(todo.id)) return;
  commit((s) => { s.todos.push(todo); });
}

export function clearDone(date) {
  const count = state.todos.filter((t) => t.date === date && t.done).length;
  if (count) commit((s) => { s.todos = s.todos.filter((t) => !(t.date === date && t.done)); });
  return count;
}

export function toggleImportant(id) {
  const todo = find(id);
  if (!todo) return;
  commit(() => { todo.important = !todo.important; });
}

// id 항목을 targetId 항목의 앞(after=false) 또는 뒤(after=true)로 옮긴다.
export function moveTodo(id, targetId, after) {
  const todo = find(id);
  if (!todo || id === targetId) return;
  const list = todosFor(todo.date).filter((t) => t.id !== id);
  const index = list.findIndex((t) => t.id === targetId);
  if (index < 0) return;
  list.splice(after ? index + 1 : index, 0, todo);
  commit(() => list.forEach((t, i) => { t.order = i; }));
}

// 이월은 복사가 아니라 이동 (PRD 11장)
export function carryOver(today) {
  const info = carryInfo();
  if (!info) return 0;
  commit((s) => {
    let order = nextOrder(today);
    const moving = s.todos
      .filter((t) => t.date === info.date && !t.done)
      .sort((a, b) => (b.important - a.important) || (a.order - b.order));
    for (const t of moving) {
      t.carriedFrom = t.carriedFrom || t.date;
      t.date = today;
      t.order = order++;
    }
    s.carryPrompt = null;
  });
  return info.count;
}

export function dismissCarry() {
  commit((s) => { s.carryPrompt = null; });
}

/* ===== 설정 ===== */

export function setFilter(filter) {
  if (!FILTERS.includes(filter) || state.settings.filter === filter) return;
  commit((s) => { s.settings.filter = filter; });
}

export function setTheme(theme) {
  if (!THEMES.includes(theme)) return;
  commit((s) => { s.settings.theme = theme; });
}

/* ===== 백업 / 정리 ===== */

export function exportData() {
  return JSON.stringify(state, null, 2);
}

export function parseBackup(text) {
  return parse(text);
}

export function replaceState(next, today) {
  commit(() => {
    state = { ...next, lastOpenedDate: today, carryPrompt: null };
  });
}

export function countBefore(date) {
  return state.todos.filter((t) => t.date < date).length;
}

export function deleteBefore(date) {
  const count = countBefore(date);
  if (count) commit((s) => { s.todos = s.todos.filter((t) => t.date >= date); });
  return count;
}
