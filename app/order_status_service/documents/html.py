def documents_app_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Document Uploads</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #fff;
      --border: #d9dee7;
      --text: #1f2937;
      --muted: #667085;
      --accent: #2563eb;
      --danger: #b42318;
      --ok: #047857;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    main {
      width: min(1040px, calc(100vw - 32px));
      margin: 28px auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0 0 4px;
      font-size: 24px;
      line-height: 1.25;
    }
    .muted { color: var(--muted); font-size: 14px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
    form {
      display: grid;
      grid-template-columns: 180px 1fr auto;
      gap: 12px;
      align-items: end;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    input, button {
      min-height: 38px;
      border-radius: 6px;
      border: 1px solid var(--border);
      font: inherit;
    }
    input { padding: 8px 10px; background: #fff; color: var(--text); }
    button {
      padding: 8px 14px;
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
      cursor: pointer;
      white-space: nowrap;
    }
    button.danger {
      border-color: var(--danger);
      background: var(--danger);
    }
    button.small {
      min-height: 32px;
      padding: 5px 10px;
      font-size: 13px;
    }
    button:disabled { opacity: .55; cursor: wait; }
    .status {
      min-height: 20px;
      margin-top: 10px;
      font-size: 14px;
    }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--ok); }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 14px;
    }
    th, td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .empty {
      padding: 28px 8px;
      text-align: center;
      color: var(--muted);
    }
    @media (max-width: 720px) {
      header { display: block; }
      form { grid-template-columns: 1fr; }
      table { display: block; overflow-x: auto; white-space: nowrap; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Загрузка документов</h1>
        <div class="muted">Документы и записи автоматически хранятся 3 дня.</div>
      </div>
      <button id="refresh" type="button">Обновить</button>
    </header>

    <section class="panel">
      <form id="upload-form">
        <label>
          Дата документа
          <input name="document_date" type="date" required>
        </label>
        <label>
          Документ
          <input name="document" type="file" required>
        </label>
        <button id="submit" type="submit">Загрузить</button>
      </form>
      <div id="status" class="status"></div>
    </section>

    <section class="panel">
      <table>
        <thead>
          <tr>
            <th style="width: 21%">Файл</th>
            <th style="width: 12%">Дата</th>
            <th style="width: 11%">Размер</th>
            <th style="width: 13%">Парсинг</th>
            <th style="width: 10%">Записи</th>
            <th style="width: 20%">Удалится</th>
            <th style="width: 13%"></th>
          </tr>
        </thead>
        <tbody id="documents"></tbody>
      </table>
      <div id="empty" class="empty" hidden>Документов пока нет.</div>
    </section>
  </main>
  <script>
    const form = document.querySelector('#upload-form');
    const submit = document.querySelector('#submit');
    const statusEl = document.querySelector('#status');
    const rowsEl = document.querySelector('#documents');
    const emptyEl = document.querySelector('#empty');
    const refreshBtn = document.querySelector('#refresh');

    function formatDateTime(value) {
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString('ru-RU');
    }

    function formatBytes(value) {
      const bytes = Number(value || 0);
      if (bytes < 1024) return `${bytes} Б`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
      return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
    }

    function setStatus(text, type = '') {
      statusEl.textContent = text;
      statusEl.className = `status ${type}`;
    }

    async function loadDocuments() {
      const response = await fetch('api/documents');
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить список');

      rowsEl.innerHTML = '';
      emptyEl.hidden = payload.documents.length > 0;
      for (const item of payload.documents) {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${escapeHtml(item.original_filename || '')}</td>
          <td>${escapeHtml(item.document_date || '')}</td>
          <td>${formatBytes(item.size_bytes)}</td>
          <td>${escapeHtml(item.parse_status || '')}</td>
          <td>${item.records_count ?? 0}</td>
          <td>${formatDateTime(item.expires_at)}</td>
          <td><button class="danger small" type="button" data-action="delete" data-id="${escapeHtml(item.id || '')}" data-name="${escapeHtml(item.original_filename || '')}">Удалить</button></td>
        `;
        rowsEl.appendChild(row);
      }
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      submit.disabled = true;
      setStatus('Загрузка...');
      try {
        const response = await fetch('api/documents', {
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

    rowsEl.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-action="delete"]');
      if (!button) return;

      const id = button.dataset.id || '';
      const name = button.dataset.name || 'документ';
      if (!confirm(`Удалить "${name}" и все записи из него?`)) return;

      button.disabled = true;
      setStatus('Удаление...');
      try {
        const response = await fetch(`api/documents/${encodeURIComponent(id)}`, {
          method: 'DELETE',
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Документ не удален');
        setStatus('Документ удален.', 'ok');
        await loadDocuments();
      } catch (error) {
        setStatus(error.message, 'error');
      } finally {
        button.disabled = false;
      }
    });

    refreshBtn.addEventListener('click', () => {
      loadDocuments().catch(error => setStatus(error.message, 'error'));
    });

    loadDocuments().catch(error => setStatus(error.message, 'error'));
  </script>
</body>
</html>"""
