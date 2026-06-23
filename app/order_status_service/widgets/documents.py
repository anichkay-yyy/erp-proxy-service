def documents_app_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Загрузка документов</title>
  <style>
    :root {
      color-scheme: light;
      --background: #fff;
      --foreground: #27272a;
      --muted: #71717a;
      --muted-soft: #a1a1aa;
      --surface: rgba(24, 24, 27, .025);
      --surface-strong: rgba(24, 24, 27, .05);
      --border: rgba(24, 24, 27, .1);
      --primary: #18181b;
      --primary-fg: #fafafa;
      --danger: #dc2626;
      --success: #059669;
      --ring: rgba(24, 24, 27, .18);
    }
    * { box-sizing: border-box; }
    html { min-width: 0; background: var(--background); }
    body {
      min-width: 0;
      margin: 0;
      background: var(--background);
      color: var(--foreground);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }
    button, input { font: inherit; }
    .shell {
      width: min(100%, 980px);
      margin: 0 auto;
      padding: clamp(16px, 3vw, 28px);
    }
    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    .eyebrow {
      margin-bottom: 6px;
      color: var(--muted-soft);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      color: var(--foreground);
      font-size: clamp(20px, 3vw, 24px);
      font-weight: 650;
      letter-spacing: 0;
      line-height: 1.18;
    }
    .subtitle {
      max-width: 620px;
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }
    .retention {
      flex: 0 0 auto;
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      padding: 6px 10px;
      font-size: 12px;
      white-space: nowrap;
    }
    .panel {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--background);
      box-shadow: 0 1px 2px rgba(24, 24, 27, .04);
    }
    .upload {
      padding: clamp(14px, 2.5vw, 18px);
    }
    .upload-grid {
      display: grid;
      grid-template-columns: minmax(150px, .75fr) minmax(240px, 1.4fr) auto;
      gap: 12px;
      align-items: end;
    }
    label {
      display: grid;
      gap: 7px;
      min-width: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }
    input {
      width: 100%;
      min-width: 0;
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--background);
      color: var(--foreground);
      padding: 8px 10px;
      outline: none;
      transition: border-color .15s ease, box-shadow .15s ease;
    }
    input:focus-visible {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--ring);
    }
    input[type="file"] {
      padding: 7px 10px;
      color: var(--muted);
    }
    input[type="file"]::file-selector-button {
      margin-right: 10px;
      border: 0;
      border-radius: 7px;
      background: var(--surface-strong);
      color: var(--foreground);
      padding: 6px 9px;
      font-weight: 500;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border: 1px solid var(--primary);
      border-radius: 8px;
      background: var(--primary);
      color: var(--primary-fg);
      padding: 8px 14px;
      font-weight: 560;
      cursor: pointer;
      white-space: nowrap;
      transition: opacity .15s ease, transform .15s ease;
    }
    .button:hover:not(:disabled) { transform: translateY(-1px); }
    .button:disabled { cursor: wait; opacity: .55; transform: none; }
    .ghost {
      border-color: transparent;
      background: transparent;
      color: var(--muted);
      padding: 6px 8px;
    }
    .status {
      min-height: 22px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--success); }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 18px 0 8px;
    }
    .section-title {
      color: var(--muted-soft);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .list {
      overflow: hidden;
    }
    .empty {
      padding: 22px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }
    .doc-row {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(110px, .7fr) minmax(96px, .6fr) auto;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
      border-top: 1px solid var(--border);
    }
    .doc-row:first-child { border-top: 0; }
    .doc-name {
      min-width: 0;
      overflow: hidden;
      color: var(--foreground);
      font-size: 13px;
      font-weight: 550;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .doc-meta {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .pill {
      justify-self: start;
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      padding: 4px 8px;
      font-size: 11px;
      white-space: nowrap;
    }
    @media (max-width: 760px) {
      .shell { padding: 16px; }
      .topbar { display: block; }
      .retention { display: inline-flex; margin-top: 12px; }
      .upload-grid { grid-template-columns: 1fr; }
      .button { width: 100%; }
      .doc-row {
        grid-template-columns: 1fr auto;
        gap: 6px 10px;
        align-items: start;
      }
      .doc-name, .doc-meta, .pill { grid-column: 1 / -1; white-space: normal; }
      .doc-row .ghost { grid-column: 2; grid-row: 1; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <div class="eyebrow">Документы доставки</div>
        <h1>Загрузка документов</h1>
        <div class="subtitle">
          Загрузите PDF за нужную дату. Mary использует эти документы, чтобы
          проверять, был ли заказ передан в доставку.
        </div>
      </div>
      <div class="retention">Хранение 3 дня</div>
    </header>

    <section class="panel upload">
      <form id="upload-form" class="upload-grid">
        <label>
          Дата документа
          <input name="document_date" type="date" required>
        </label>
        <label>
          PDF-документ
          <input name="document" type="file" accept="application/pdf,.pdf" required>
        </label>
        <button id="submit" class="button" type="submit">Загрузить</button>
      </form>
      <div id="status" class="status" role="status" aria-live="polite"></div>
    </section>

    <div class="section-head">
      <div class="section-title">Последние документы</div>
      <button id="refresh" class="button ghost" type="button">Обновить</button>
    </div>
    <section id="documents" class="panel list">
      <div class="empty">Загружаю список документов...</div>
    </section>
  </main>

  <script>
    const form = document.querySelector('#upload-form');
    const submit = document.querySelector('#submit');
    const refresh = document.querySelector('#refresh');
    const statusEl = document.querySelector('#status');
    const documentsEl = document.querySelector('#documents');

    function widgetApiPath() {
      const path = window.location.pathname.endsWith('/')
        ? window.location.pathname
        : `${window.location.pathname}/`;
      return new URL('api/documents', `${window.location.origin}${path}`).pathname;
    }

    const documentsApi = widgetApiPath();

    function setStatus(text, type = '') {
      statusEl.textContent = text;
      statusEl.className = `status ${type}`;
    }

    function formatBytes(value) {
      if (!Number.isFinite(value)) return '';
      if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} КБ`;
      return `${(value / 1024 / 1024).toFixed(1)} МБ`;
    }

    function formatDate(value) {
      if (!value) return '';
      try {
        return new Intl.DateTimeFormat('ru-RU').format(new Date(value));
      } catch {
        return value;
      }
    }

    function renderDocuments(items) {
      if (!items.length) {
        documentsEl.innerHTML = '<div class="empty">Документы пока не загружены.</div>';
        return;
      }
      documentsEl.innerHTML = items.map((doc) => `
        <article class="doc-row">
          <div class="doc-name" title="${escapeHtml(doc.original_filename || 'Документ')}">
            ${escapeHtml(doc.original_filename || 'Документ')}
          </div>
          <div class="doc-meta">${escapeHtml(formatDate(doc.document_date))}</div>
          <div class="pill">${Number(doc.records_count || 0)} записей</div>
          <button class="button ghost" type="button" data-delete="${escapeHtml(doc.id)}">
            Удалить
          </button>
          <div class="doc-meta">
            ${escapeHtml(formatBytes(Number(doc.size_bytes)))} · до ${escapeHtml(formatDate(doc.expires_at))}
          </div>
        </article>
      `).join('');
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));
    }

    async function loadDocuments() {
      try {
        const response = await fetch(`${documentsApi}?limit=20`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Список недоступен');
        renderDocuments(payload.documents || []);
      } catch (error) {
        documentsEl.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      }
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      submit.disabled = true;
      setStatus('Загружаю документ...');
      try {
        const response = await fetch(documentsApi, {
          method: 'POST',
          body: new FormData(form),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Документ не загружен');
        form.reset();
        setStatus('Документ загружен и обработан.', 'ok');
        await loadDocuments();
      } catch (error) {
        setStatus(error.message, 'error');
      } finally {
        submit.disabled = false;
      }
    });

    refresh.addEventListener('click', () => {
      void loadDocuments();
    });

    documentsEl.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-delete]');
      if (!button) return;
      button.disabled = true;
      try {
        const response = await fetch(`${documentsApi}/${button.dataset.delete}`, {
          method: 'DELETE',
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Документ не удалён');
        setStatus('Документ удалён.', 'ok');
        await loadDocuments();
      } catch (error) {
        setStatus(error.message, 'error');
        button.disabled = false;
      }
    });

    void loadDocuments();
  </script>
</body>
</html>"""
