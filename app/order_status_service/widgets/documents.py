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
    button:disabled { opacity: .55; cursor: wait; }
    .status {
      min-height: 20px;
      margin-top: 10px;
      font-size: 14px;
    }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--ok); }
    @media (max-width: 720px) {
      form { grid-template-columns: 1fr; }
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
  </main>
  <script>
    const form = document.querySelector('#upload-form');
    const submit = document.querySelector('#submit');
    const statusEl = document.querySelector('#status');

    function setStatus(text, type = '') {
      statusEl.textContent = text;
      statusEl.className = `status ${type}`;
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      submit.disabled = true;
      setStatus('Загрузка...');
      try {
        const response = await fetch('/api/documents', {
          method: 'POST',
          body: new FormData(form),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Документ не загружен');
        form.reset();
        setStatus('Документ загружен и обработан.', 'ok');
      } catch (error) {
        setStatus(error.message, 'error');
      } finally {
        submit.disabled = false;
      }
    });
  </script>
</body>
</html>"""
