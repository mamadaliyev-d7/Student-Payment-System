/* Учёт учеников, оплат и задолженностей — клиентская часть.
   Все данные берутся из REST API того же сервера. Текст из API всегда вставляется
   через DOM (textContent), а не через innerHTML, поэтому разметка в именах не выполняется. */
(() => {
  'use strict';

  const MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  const MAX_AMOUNT = 1000000000000;
  const MONTH_RE = /^(20[0-9]{2}|2100)-(0[1-9]|1[0-2])$/;

  const state = {
    month: currentMonth(),
    students: [],
    filters: { search: '', group: '' },
    historyStudentId: null,
  };
  let renderSeq = 0;
  let hintSeq = 0;

  const $ = (selector, root = document) => root.querySelector(selector);

  /* ------------------------------------------------------------------ утилиты */
  function pad(n) { return String(n).padStart(2, '0'); }
  function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function currentMonth() { return todayISO().slice(0, 7); }
  function shiftMonth(month, delta) {
    let [year, m] = month.split('-').map(Number);
    m += delta;
    while (m > 12) { m -= 12; year += 1; }
    while (m < 1) { m += 12; year -= 1; }
    return `${year}-${pad(m)}`;
  }
  function monthLabel(month) {
    const [year, m] = month.split('-').map(Number);
    return `${MONTH_NAMES[m - 1]} ${year}`;
  }
  function lastDayOfMonth(month) {
    const [year, m] = month.split('-').map(Number);
    return `${month}-${pad(new Date(year, m, 0).getDate())}`;
  }
  const numberFormat = new Intl.NumberFormat('ru-RU');
  function fmtNum(n) { return numberFormat.format(n); }
  function money(n) { return `${fmtNum(n)} сум`; }
  function fmtDate(iso) {
    const [y, m, d] = iso.split('-');
    return `${d}.${m}.${y}`;
  }
  function byName(a, b) { return a.name.localeCompare(b.name, 'ru') || a.id - b.id; }
  function sum(items, pick) { return items.reduce((total, item) => total + pick(item), 0); }

  /** Создаёт DOM-элемент. Строки-потомки вставляются как текст. */
  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value === null || value === undefined || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value === true ? '' : String(value));
      }
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child);
    }
    return node;
  }

  /* ---------------------------------------------------------------------- API */
  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  async function api(path, { method = 'GET', body } = {}) {
    let response;
    try {
      response = await fetch(path, {
        method,
        headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (_) {
      throw new ApiError('Нет связи с сервером. Проверьте, что приложение запущено.', 0);
    }
    if (response.status === 204) return null;
    let data = null;
    try { data = await response.json(); } catch (_) { /* тело не JSON */ }
    if (!response.ok) {
      let message = `Ошибка сервера (${response.status})`;
      if (data && typeof data.detail === 'string') message = data.detail;
      else if (data && Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join('; ');
      throw new ApiError(message, response.status);
    }
    return data;
  }

  const q = encodeURIComponent;

  /* ------------------------------------------------------- общие блоки интерфейса */
  function loadingEl() {
    return el('div', { class: 'state', role: 'status' },
      el('div', { class: 'spinner', 'aria-hidden': 'true' }),
      el('p', { class: 'state-text' }, 'Загрузка…'));
  }

  function errorEl(error, retry) {
    return el('div', { class: 'state state-error', role: 'alert' },
      el('p', { class: 'state-title' }, 'Не удалось загрузить данные'),
      el('p', { class: 'state-text' }, error.message),
      el('button', { type: 'button', class: 'btn', onclick: retry }, 'Повторить'));
  }

  function emptyEl(title, text, action) {
    return el('div', { class: 'state' },
      el('p', { class: 'state-title' }, title),
      text ? el('p', { class: 'state-text' }, text) : null,
      action || null);
  }

  function debtMeter(paid, fee) {
    const percent = fee > 0 ? Math.min(100, Math.round((paid / fee) * 100)) : 100;
    const bar = el('span');
    bar.style.width = `${percent}%`;
    return el('div', { class: 'meter', role: 'img', 'aria-label': `Оплачено ${percent}%` }, bar);
  }

  function toast(message, type = 'success') {
    const node = el('div', { class: `toast toast-${type}`, role: type === 'error' ? 'alert' : 'status' }, message);
    $('#toasts').append(node);
    setTimeout(() => node.remove(), type === 'error' ? 6000 : 3500);
  }

  function setBusy(button, busy) {
    button.disabled = busy;
    button.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  /* ---------------------------------------------------------- маршрутизация */
  const ROUTES = {
    dashboard: { title: 'Дашборд', view: dashboardView },
    students: { title: 'Ученики', view: studentsView },
    debtors: { title: 'Должники', view: debtorsView },
  };

  function currentRoute() {
    const name = location.hash.replace(/^#\/?/, '').split('?')[0];
    return ROUTES[name] ? name : 'dashboard';
  }

  function syncMonthControl() {
    const input = $('#month-input');
    if (input.value !== state.month) input.value = state.month;
  }

  async function render({ keep = false } = {}) {
    const seq = ++renderSeq;
    const name = currentRoute();
    const route = ROUTES[name];
    const view = $('#view');

    document.title = `${route.title} — Учёт оплат`;
    $('#page-title').textContent = route.title;
    document.querySelectorAll('[data-route]').forEach((link) => {
      if (link.dataset.route === name) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    syncMonthControl();

    // При обновлении после действия оставляем старое содержимое, чтобы не мигало.
    if (!keep || view.dataset.route !== name) view.replaceChildren(loadingEl());
    view.dataset.route = name;
    view.setAttribute('aria-busy', 'true');

    try {
      const node = await route.view();
      if (seq !== renderSeq) return;
      view.replaceChildren(node);
    } catch (error) {
      if (seq !== renderSeq) return;
      view.replaceChildren(errorEl(error, () => render()));
    } finally {
      if (seq === renderSeq) view.removeAttribute('aria-busy');
    }
  }

  /** Перерисовывает текущий экран и, если открыта, историю оплат. */
  async function refresh() {
    const tasks = [render({ keep: true })];
    if (state.historyStudentId !== null && $('#history-dialog').open) tasks.push(renderHistory());
    await Promise.all(tasks);
  }

  /* --------------------------------------------------------------- Дашборд */
  async function dashboardView() {
    const month = state.month;
    const [summary, debtors, payments, students] = await Promise.all([
      api(`/dashboard?month=${q(month)}`),
      api(`/debtors?month=${q(month)}`),
      api(`/payments?month=${q(month)}`),
      api('/students'),
    ]);
    state.students = students;
    const label = monthLabel(month);

    const stat = (title, value, { unit = false, debt = false } = {}) => el('div', { class: 'stat' },
      el('div', { class: 'stat-label' }, title),
      el('div', { class: `stat-value${debt ? ' is-debt' : ''}` },
        fmtNum(value), unit ? el('span', { class: 'unit' }, 'сум') : null));

    const root = el('div', { class: 'stack' },
      el('div', { class: 'stats' },
        stat('Всего учеников', summary.total_students),
        stat('Должников за месяц', summary.total_debtors),
        stat('Общая задолженность', summary.total_debt, { unit: true, debt: summary.total_debt > 0 }),
        stat('Получено за месяц', summary.total_received, { unit: true })));

    if (summary.total_students === 0) {
      root.append(emptyEl('Пока нет учеников',
        'Добавьте первого ученика — после этого можно вносить оплаты и следить за долгами.',
        el('button', { type: 'button', class: 'btn primary', onclick: () => openStudentDialog() }, 'Добавить ученика')));
      return root;
    }

    const studentName = (id) => (students.find((s) => s.id === id) || {}).name || `Ученик №${id}`;
    const topDebtors = [...debtors.debtors].sort((a, b) => b.debt_amount - a.debt_amount).slice(0, 5);

    const debtsPanel = el('section', { class: 'panel' },
      el('div', { class: 'panel-head' },
        el('h2', null, 'Крупнейшие долги'),
        el('a', { href: '#/debtors' }, 'Все должники')),
      topDebtors.length
        ? el('ul', { class: 'list' }, topDebtors.map((d) => el('li', { class: 'list-row' },
          el('div', { class: 'row-main' },
            el('span', { class: 'row-title' }, d.name),
            el('span', { class: 'row-amount is-debt' }, money(d.debt_amount))),
          el('div', { class: 'row-sub' }, `${d.group_name}, оплачено ${money(d.paid_amount)} из ${money(d.monthly_fee)}`),
          debtMeter(d.paid_amount, d.monthly_fee))))
        : emptyEl('Долгов нет', `Все ученики оплатили ${label.toLowerCase()}.`));

    const recent = payments.slice(0, 6);
    const paymentsPanel = el('section', { class: 'panel' },
      el('div', { class: 'panel-head' }, el('h2', null, 'Последние оплаты')),
      recent.length
        ? el('ul', { class: 'list' }, recent.map((p) => el('li', { class: 'list-row' },
          el('div', { class: 'row-main' },
            el('span', { class: 'row-title' }, studentName(p.student_id)),
            el('span', { class: 'row-amount' }, money(p.amount))),
          el('div', { class: 'row-sub' }, fmtDate(p.payment_date)))))
        : emptyEl('Оплат пока нет', `За ${label.toLowerCase()} ещё не было платежей.`));

    root.append(el('div', { class: 'columns' }, debtsPanel, paymentsPanel));
    return root;
  }

  /* -------------------------------------------------------------- Ученики */
  async function studentsView() {
    const [students, debtorsData] = await Promise.all([
      api('/students'),
      api(`/debtors?month=${q(state.month)}`),
    ]);
    state.students = students;
    const debtByStudent = new Map(debtorsData.debtors.map((d) => [d.student_id, d]));
    const filters = state.filters;
    const groups = [...new Set(students.map((s) => s.group_name))].sort((a, b) => a.localeCompare(b, 'ru'));
    if (filters.group && !groups.includes(filters.group)) filters.group = '';

    const search = el('input', {
      type: 'search', class: 'search', placeholder: 'Поиск по имени или телефону',
      'aria-label': 'Поиск по имени или телефону', autocomplete: 'off', value: filters.search,
    });
    const groupSelect = el('select', { 'aria-label': 'Фильтр по группе' },
      el('option', { value: '' }, 'Все группы'),
      groups.map((g) => el('option', { value: g }, g)));
    groupSelect.value = filters.group;

    const tbody = el('tbody');
    const table = el('table', { class: 'data' },
      el('thead', null, el('tr', null,
        el('th', { scope: 'col' }, 'Ученик'),
        el('th', { scope: 'col' }, 'Группа'),
        el('th', { scope: 'col', class: 'right' }, 'В месяц'),
        el('th', { scope: 'col' }, `Оплата за ${monthLabel(state.month).toLowerCase()}`),
        el('th', { scope: 'col' }, el('span', { class: 'sr-only' }, 'Действия')))),
      tbody);
    const tableWrap = el('div', { class: 'table-wrap' }, table);
    const emptyBox = el('div');
    const countLine = el('p', { class: 'muted count-line', 'aria-live': 'polite' });

    function matches(student) {
      if (filters.group && student.group_name !== filters.group) return false;
      const query = filters.search.trim().toLowerCase();
      if (!query) return true;
      if (student.name.toLowerCase().includes(query)) return true;
      // По телефону ищем, только если запрос похож на номер (цифры, +, пробелы, скобки, дефисы).
      if (/^[0-9\s+\-()]+$/.test(query)) {
        const digits = query.replace(/[^0-9]/g, '');
        return digits ? student.phone.replace(/[^0-9]/g, '').includes(digits) : false;
      }
      return false;
    }

    function statusBadge(student) {
      const debtor = debtByStudent.get(student.id);
      if (debtor) return el('span', { class: 'badge badge-debt' }, `Долг ${money(debtor.debt_amount)}`);
      if (student.monthly_fee === 0) return el('span', { class: 'badge badge-muted' }, 'Без платы');
      return el('span', { class: 'badge badge-ok' }, 'Оплачено');
    }

    function renderRows() {
      const list = students.filter(matches).sort(byName);
      tbody.replaceChildren(...list.map((s) => el('tr', { class: debtByStudent.has(s.id) ? 'is-debtor' : null },
        el('td', { class: 'cell-main' },
          el('div', { class: 'name' }, s.name),
          el('a', { class: 'sub', href: `tel:${s.phone.replace(/[^0-9+]/g, '')}` }, s.phone)),
        el('td', { 'data-label': 'Группа' }, s.group_name),
        el('td', { class: 'money right', 'data-label': 'В месяц' }, money(s.monthly_fee)),
        el('td', { 'data-label': 'За месяц' }, statusBadge(s)),
        el('td', { class: 'cell-actions-wrap' },
          el('div', { class: 'cell-actions' },
            el('button', { type: 'button', class: 'btn sm primary', onclick: () => openPaymentDialog({ studentId: s.id }) }, 'Оплата'),
            el('button', { type: 'button', class: 'btn sm', onclick: () => openHistory(s.id) }, 'История'),
            el('button', { type: 'button', class: 'btn sm', onclick: () => openStudentDialog(s) }, 'Изменить'),
            el('button', { type: 'button', class: 'btn sm danger', onclick: () => deleteStudent(s) }, 'Удалить'))))));

      tableWrap.hidden = list.length === 0;
      emptyBox.replaceChildren();
      if (students.length === 0) {
        emptyBox.append(emptyEl('Учеников пока нет', 'Нажмите «Добавить ученика», чтобы создать первую запись.'));
      } else if (list.length === 0) {
        emptyBox.append(emptyEl('Ничего не найдено', 'Измените поисковый запрос или сбросьте фильтр по группе.'));
      }
      countLine.textContent = students.length ? `Показано ${list.length} из ${students.length}` : '';
    }

    search.addEventListener('input', () => { filters.search = search.value; renderRows(); });
    groupSelect.addEventListener('change', () => { filters.group = groupSelect.value; renderRows(); });
    renderRows();

    return el('div', { class: 'stack' },
      el('div', { class: 'toolbar' }, search, groupSelect,
        el('button', { type: 'button', class: 'btn primary', onclick: () => openStudentDialog() }, 'Добавить ученика')),
      countLine, tableWrap, emptyBox);
  }

  /* ------------------------------------------------------------- Должники */
  async function debtorsView() {
    const data = await api(`/debtors?month=${q(state.month)}`);
    const label = monthLabel(state.month);
    const debtors = [...data.debtors].sort((a, b) => b.debt_amount - a.debt_amount || a.name.localeCompare(b.name, 'ru'));

    if (debtors.length === 0) {
      return emptyEl(`Должников за ${label.toLowerCase()} нет`,
        'Все ученики оплатили месяц полностью — или в системе пока нет учеников.');
    }

    const payDate = state.month === currentMonth() ? null : lastDayOfMonth(state.month);
    const rows = debtors.map((d) => el('tr', { class: 'is-debtor' },
      el('td', { class: 'cell-main' },
        el('div', { class: 'name' }, d.name),
        el('a', { class: 'sub', href: `tel:${d.phone.replace(/[^0-9+]/g, '')}` }, d.phone)),
      el('td', { 'data-label': 'Группа' }, d.group_name),
      el('td', { class: 'money right', 'data-label': 'Стоимость' }, money(d.monthly_fee)),
      el('td', { class: 'money right', 'data-label': 'Оплачено' }, money(d.paid_amount)),
      el('td', { class: 'right', 'data-label': 'Остаток' },
        el('div', { class: 'debt-cell' },
          el('span', { class: 'debt-amount num' }, money(d.debt_amount)),
          debtMeter(d.paid_amount, d.monthly_fee))),
      el('td', { class: 'cell-actions-wrap' },
        el('div', { class: 'cell-actions' },
          el('button', {
            type: 'button', class: 'btn sm primary',
            onclick: () => openPaymentDialog({ studentId: d.student_id, amount: d.debt_amount, date: payDate }),
          }, 'Оплата'),
          el('button', { type: 'button', class: 'btn sm', onclick: () => openHistory(d.student_id) }, 'История')))));

    return el('div', { class: 'stack' },
      el('div', { class: 'summary' },
        el('span', null, `Должников: `, el('strong', null, fmtNum(data.total_debtors))),
        el('span', null, 'Общая задолженность: ', el('strong', { class: 'is-debt' }, money(data.total_debt)))),
      el('div', { class: 'table-wrap' },
        el('table', { class: 'data' },
          el('thead', null, el('tr', null,
            el('th', { scope: 'col' }, 'Ученик'),
            el('th', { scope: 'col' }, 'Группа'),
            el('th', { scope: 'col', class: 'right' }, 'Стоимость'),
            el('th', { scope: 'col', class: 'right' }, 'Оплачено'),
            el('th', { scope: 'col', class: 'right' }, 'Остаток'),
            el('th', { scope: 'col' }, el('span', { class: 'sr-only' }, 'Действия')))),
          el('tbody', null, rows),
          el('tfoot', null, el('tr', null,
            el('td', { class: 'cell-main' }, 'Итого к получению'),
            el('td'), el('td'), el('td'),
            el('td', { class: 'money right debt-amount', 'data-label': 'Итого к получению' }, money(data.total_debt)),
            el('td'))))));
  }

  /* ------------------------------------------------------ Валидация форм */
  function setFieldError(input, message) {
    const field = input.closest('.field');
    const errorNode = field.querySelector('.field-error');
    errorNode.textContent = message || '';
    errorNode.hidden = !message;
    input.setAttribute('aria-invalid', message ? 'true' : 'false');
    return !message;
  }

  function showFormError(selector, message) {
    const box = $(selector);
    box.textContent = message || '';
    box.hidden = !message;
  }

  function checkAmount(input, { allowZero }) {
    const raw = input.value.trim();
    if (raw === '') return { error: 'Укажите сумму' };
    const value = Number(raw);
    if (!Number.isInteger(value)) return { error: 'Введите целое число, без копеек' };
    if (value < 0 || (!allowZero && value === 0)) {
      return { error: allowZero ? 'Стоимость не может быть отрицательной' : 'Сумма должна быть больше нуля' };
    }
    if (value > MAX_AMOUNT) return { error: 'Слишком большая сумма' };
    return { value };
  }

  function bindAmountPreview(input, previewSelector) {
    const preview = $(previewSelector);
    const update = () => {
      const raw = input.value.trim();
      const value = Number(raw);
      preview.textContent = raw !== '' && Number.isInteger(value) && value >= 0 ? money(value) : '';
    };
    input.addEventListener('input', update);
    return update;
  }

  /* ---------------------------------------------------- Диалог ученика */
  const updateFeePreview = bindAmountPreview($('#student-fee'), '#student-fee-preview');

  function openStudentDialog(student = null) {
    const form = $('#student-form');
    form.reset();
    form.querySelectorAll('input').forEach((input) => setFieldError(input, ''));
    showFormError('#student-form-error', '');
    form.dataset.studentId = student ? String(student.id) : '';

    $('#student-dialog-title').textContent = student ? 'Изменить ученика' : 'Новый ученик';
    $('#student-submit').textContent = student ? 'Сохранить изменения' : 'Добавить ученика';

    const groups = [...new Set(state.students.map((s) => s.group_name))].sort((a, b) => a.localeCompare(b, 'ru'));
    $('#group-options').replaceChildren(...groups.map((g) => el('option', { value: g })));

    if (student) {
      $('#student-name').value = student.name;
      $('#student-phone').value = student.phone;
      $('#student-group').value = student.group_name;
      $('#student-fee').value = String(student.monthly_fee);
    }
    updateFeePreview();
    $('#student-dialog').showModal();
  }

  function readStudentForm() {
    const nameInput = $('#student-name');
    const phoneInput = $('#student-phone');
    const groupInput = $('#student-group');
    const feeInput = $('#student-fee');

    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const group = groupInput.value.trim();
    const digits = phone.replace(/[^0-9]/g, '');
    const fee = checkAmount(feeInput, { allowZero: true });

    const results = [
      setFieldError(nameInput, !name ? 'Введите имя ученика' : name.length > 100 ? 'Не более 100 символов' : ''),
      setFieldError(phoneInput,
        !phone ? 'Введите номер телефона'
          : !/^\+?[0-9\s\-()]+$/.test(phone) || digits.length < 7 || digits.length > 15
            ? 'Некорректный номер. Пример: +998 90 123 45 67' : ''),
      setFieldError(groupInput, !group ? 'Укажите группу' : group.length > 100 ? 'Не более 100 символов' : ''),
      setFieldError(feeInput, fee.error || ''),
    ];
    if (results.includes(false)) {
      const firstInvalid = document.querySelector('#student-form [aria-invalid="true"]');
      if (firstInvalid) firstInvalid.focus();
      return null;
    }
    return { name, phone, group_name: group, monthly_fee: fee.value };
  }

  $('#student-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    showFormError('#student-form-error', '');
    const data = readStudentForm();
    if (!data) return;

    const studentId = event.currentTarget.dataset.studentId;
    const submit = $('#student-submit');
    setBusy(submit, true);
    try {
      if (studentId) await api(`/students/${studentId}`, { method: 'PATCH', body: data });
      else await api('/students', { method: 'POST', body: data });
      $('#student-dialog').close();
      toast(studentId ? 'Изменения сохранены' : 'Ученик добавлен');
      await refresh();
    } catch (error) {
      showFormError('#student-form-error', error.message);
    } finally {
      setBusy(submit, false);
    }
  });

  async function deleteStudent(student) {
    let extra = ' Также будут удалены все его оплаты.';
    try {
      const payments = await api(`/students/${student.id}/payments`);
      extra = payments.length
        ? ` Также будут удалены его оплаты: ${payments.length} шт. на сумму ${money(sum(payments, (p) => p.amount))}.`
        : '';
    } catch (_) { /* оставляем общий текст предупреждения */ }

    const confirmed = await confirmDialog({
      title: 'Удалить ученика?',
      message: `«${student.name}» (${student.group_name}) будет удалён.${extra} Это действие нельзя отменить.`,
      confirmText: 'Удалить',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api(`/students/${student.id}`, { method: 'DELETE' });
      toast('Ученик удалён');
      await refresh();
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function confirmDialog({ title, message, confirmText = 'Подтвердить', danger = false }) {
    return new Promise((resolve) => {
      const dialog = $('#confirm-dialog');
      const okButton = $('#confirm-ok');
      $('#confirm-title').textContent = title;
      $('#confirm-message').textContent = message;
      okButton.textContent = confirmText;
      okButton.className = `btn ${danger ? 'danger-solid' : 'primary'}`;

      let result = false;
      const onOk = () => { result = true; dialog.close(); };
      const onClose = () => {
        okButton.removeEventListener('click', onOk);
        dialog.removeEventListener('close', onClose);
        resolve(result);
      };
      okButton.addEventListener('click', onOk);
      dialog.addEventListener('close', onClose);
      dialog.showModal();
    });
  }

  /* ----------------------------------------------------- Диалог оплаты */
  const updateAmountPreview = bindAmountPreview($('#payment-amount'), '#payment-amount-preview');

  async function openPaymentDialog({ studentId = null, amount = null, date = null } = {}) {
    if (state.students.length === 0) {
      try { state.students = await api('/students'); } catch (error) { toast(error.message, 'error'); return; }
    }
    if (state.students.length === 0) {
      toast('Сначала добавьте хотя бы одного ученика', 'error');
      return;
    }

    const form = $('#payment-form');
    form.reset();
    form.querySelectorAll('input, select').forEach((input) => setFieldError(input, ''));
    showFormError('#payment-form-error', '');

    const select = $('#payment-student');
    select.replaceChildren(
      el('option', { value: '' }, 'Выберите ученика'),
      ...[...state.students].sort(byName).map((s) => el('option', { value: String(s.id) }, `${s.name} (${s.group_name})`)));
    select.value = studentId ? String(studentId) : '';
    $('#payment-amount').value = amount ? String(amount) : '';
    $('#payment-date').value = date || todayISO();
    updateAmountPreview();

    $('#payment-hint').hidden = true;
    $('#payment-dialog').showModal();
    updatePaymentHint();
  }

  /** Подсказка: сколько ученик уже внёс за месяц выбранной даты и сколько осталось. */
  async function updatePaymentHint() {
    const hint = $('#payment-hint');
    const seq = ++hintSeq;
    const studentId = Number($('#payment-student').value);
    const date = $('#payment-date').value;
    const student = state.students.find((s) => s.id === studentId);

    if (!student || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(date) || !MONTH_RE.test(date.slice(0, 7))) {
      hint.hidden = true;
      return;
    }
    const month = date.slice(0, 7);
    try {
      const payments = await api(`/students/${studentId}/payments?month=${q(month)}`);
      if (seq !== hintSeq) return;
      const paid = sum(payments, (p) => p.amount);
      const remaining = Math.max(student.monthly_fee - paid, 0);
      hint.replaceChildren(
        el('div', null, `Оплата засчитается в ${monthLabel(month).toLowerCase()}.`),
        el('div', null, 'Внесено за месяц: ', el('strong', null, money(paid)), ' из ', el('strong', null, money(student.monthly_fee)), '.'),
        remaining > 0
          ? el('button', {
            type: 'button', class: 'btn sm',
            onclick: () => { $('#payment-amount').value = String(remaining); updateAmountPreview(); setFieldError($('#payment-amount'), ''); },
          }, `Внести остаток ${money(remaining)}`)
          : el('div', null, 'Месяц оплачен полностью.'));
      hint.hidden = false;
    } catch (_) {
      if (seq === hintSeq) hint.hidden = true;
    }
  }

  $('#payment-student').addEventListener('change', updatePaymentHint);
  $('#payment-date').addEventListener('change', updatePaymentHint);

  $('#payment-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    showFormError('#payment-form-error', '');

    const studentInput = $('#payment-student');
    const amountInput = $('#payment-amount');
    const dateInput = $('#payment-date');
    const amount = checkAmount(amountInput, { allowZero: false });
    const date = dateInput.value;
    const dateError = !date ? 'Укажите дату оплаты'
      : !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(date) || !MONTH_RE.test(date.slice(0, 7)) ? 'Некорректная дата (годы 2000–2100)' : '';

    const results = [
      setFieldError(studentInput, studentInput.value ? '' : 'Выберите ученика'),
      setFieldError(amountInput, amount.error || ''),
      setFieldError(dateInput, dateError),
    ];
    if (results.includes(false)) {
      const firstInvalid = document.querySelector('#payment-form [aria-invalid="true"]');
      if (firstInvalid) firstInvalid.focus();
      return;
    }

    const submit = $('#payment-submit');
    setBusy(submit, true);
    try {
      await api('/payments', {
        method: 'POST',
        body: { student_id: Number(studentInput.value), amount: amount.value, payment_date: date },
      });
      $('#payment-dialog').close();
      toast(`Оплата ${money(amount.value)} сохранена`);
      await refresh();
    } catch (error) {
      showFormError('#payment-form-error', error.message);
    } finally {
      setBusy(submit, false);
    }
  });

  /* --------------------------------------------------- История оплат */
  async function openHistory(studentId) {
    state.historyStudentId = studentId;
    $('#history-title').textContent = 'История оплат';
    $('#history-sub').textContent = '';
    $('#history-body').replaceChildren(loadingEl());
    $('#history-dialog').showModal();
    await renderHistory();
  }

  async function renderHistory() {
    const studentId = state.historyStudentId;
    const body = $('#history-body');
    try {
      const [student, payments] = await Promise.all([
        api(`/students/${studentId}`),
        api(`/students/${studentId}/payments`),
      ]);
      if (state.historyStudentId !== studentId) return;

      $('#history-title').textContent = student.name;
      $('#history-sub').textContent = `${student.group_name}, ${money(student.monthly_fee)} в месяц`;

      if (payments.length === 0) {
        body.replaceChildren(emptyEl('Оплат пока нет', 'Когда ученик внесёт первую оплату, она появится здесь.'));
      } else {
        const byMonth = new Map();
        for (const payment of payments) {
          const key = payment.payment_date.slice(0, 7);
          if (!byMonth.has(key)) byMonth.set(key, []);
          byMonth.get(key).push(payment);
        }
        const sections = [...byMonth.entries()].map(([key, items]) => {
          const paid = sum(items, (p) => p.amount);
          const badge = paid >= student.monthly_fee
            ? el('span', { class: 'badge badge-ok' }, 'Оплачено полностью')
            : el('span', { class: 'badge badge-debt' }, `Не хватает ${money(student.monthly_fee - paid)}`);
          return el('section', { class: 'history-month' },
            el('div', { class: 'history-month-head' },
              el('h3', null, `${monthLabel(key)}: ${money(paid)}`), badge),
            items.map((p) => el('div', { class: 'history-row' },
              el('span', null, fmtDate(p.payment_date)),
              el('strong', null, money(p.amount)))));
        });
        body.replaceChildren(
          el('p', { class: 'muted history-total' },
            `Всего оплат: ${payments.length}, на сумму ${money(sum(payments, (p) => p.amount))}`),
          ...sections);
      }
    } catch (error) {
      if (state.historyStudentId === studentId) body.replaceChildren(errorEl(error, renderHistory));
    }
  }

  $('#history-add').addEventListener('click', () => {
    if (state.historyStudentId !== null) openPaymentDialog({ studentId: state.historyStudentId });
  });
  $('#history-dialog').addEventListener('close', () => { state.historyStudentId = null; });

  /* ---------------------------------------------- Общие обработчики */
  document.addEventListener('click', (event) => {
    const closer = event.target.closest('[data-close]');
    if (closer) closer.closest('dialog').close();
  });

  $('#btn-add-payment').addEventListener('click', () => openPaymentDialog());

  function setMonth(value) {
    if (!MONTH_RE.test(value)) { syncMonthControl(); return; }
    state.month = value;
    render();
  }
  $('#month-prev').addEventListener('click', () => setMonth(shiftMonth(state.month, -1)));
  $('#month-next').addEventListener('click', () => setMonth(shiftMonth(state.month, 1)));
  $('#month-input').addEventListener('change', (event) => setMonth(event.target.value));

  window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
  render();
})();
