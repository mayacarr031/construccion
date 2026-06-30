// ── Predictor en tiempo real ──────────────────────────────────────────────────
async function enviarDatos() {
  const text = document.getElementById('textInput').value.trim();
  const btn = document.getElementById('analyzeBtn');
  const spinner = document.getElementById('spinner');
  const resBox = document.getElementById('resultado');

  if (!text) {
    alert('Por favor escribe un texto antes de analizar.');
    return;
  }

  btn.classList.add('loading');
  btn.querySelector('.btn-label').textContent = 'Analizando...';
  spinner.style.display = 'block';
  resBox.style.display = 'none';

  try {
    const response = await fetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (response.status === 401 || response.status === 403 || response.status === 303) {
      alert('Sesión inválida o expirada. Por favor ingresa de nuevo.');
      window.location.href = '/login';
      return;
    }
    if (!response.ok) throw new Error(`Error del servidor: ${response.status}`);

    const data = await response.json();
    renderResultado(data, resBox);

  } catch (err) {
    console.error(err);
    resBox.style.display = 'block';
    resBox.className = 'result-box';
    resBox.innerHTML = `<p style="color:#ef4444;">⚠️ Error: ${err.message}</p>`;
  } finally {
    btn.classList.remove('loading');
    btn.querySelector('.btn-label').textContent = 'Analizar Sentimiento';
    spinner.style.display = 'none';
  }
}

function renderResultado(data, container) {
  const sentiment = data.sentiment;          // 'POSITIVE' | 'NEGATIVE'
  const confidencePct = (data.confidence * 100).toFixed(1);
  const icon = sentiment === 'POSITIVE' ? '😊' : '😞';

  container.className = `result-box ${sentiment}`;
  container.innerHTML = `
    <div class="result-label ${sentiment}">${icon} ${sentiment}</div>
    <div style="font-size:0.8rem;color:#94a3b8;margin-bottom:6px;">Nivel de confianza</div>
    <div class="confidence-bar-wrap">
      <div class="confidence-bar-fill" style="width:0%"></div>
    </div>
    <div style="font-size:0.85rem;color:#cbd5e1;margin-top:4px;">${confidencePct}%</div>
    <div style="font-size:0.78rem;color:#94a3b8;margin-top:10px;word-break:break-word;">
      <strong>Texto analizado:</strong> "${data.text.slice(0, 120)}${data.text.length > 120 ? '…' : ''}"
    </div>`;
  container.style.display = 'block';

  setTimeout(() => {
    const fill = container.querySelector('.confidence-bar-fill');
    if (fill) fill.style.width = `${confidencePct}%`;
  }, 50);
}

// ── Dataset Kaggle Loader ─────────────────────────────────────────────────────
async function cargarDataset() {
  const loadBtn = document.getElementById('loadBtn');
  const container = document.getElementById('dataset-container');

  loadBtn.disabled = true;
  loadBtn.innerHTML = '⏳ Cargando...';
  container.innerHTML = '<p style="color:#94a3b8;font-size:0.875rem;text-align:center;padding:32px 0;">⏳ Ejecutando inferencia local sobre el dataset de Kaggle...</p>';

  try {
    const response = await fetch('/api/dataset');
    if (!response.ok) throw new Error(`Error ${response.status}`);
    const rows = await response.json();
    renderDatasetTable(rows, container);
  } catch (err) {
    container.innerHTML = `<p style="color:#ef4444;font-size:0.875rem;text-align:center;padding:32px 0;">⚠️ Error al cargar: ${err.message}</p>`;
  } finally {
    loadBtn.disabled = false;
    loadBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1rem;">refresh</span> Recargar';
  }
}

function renderDatasetTable(rows, container) {
  const sentimentBadge = (label) => {
    const cls = {
      'Positive': 'badge-pos', 'POSITIVE': 'badge-pos',
      'Negative': 'badge-neg', 'NEGATIVE': 'badge-neg',
      'Neutral': 'badge-neu', 'Irrelevant': 'badge-irr'
    }[label] || 'badge-neu';
    return `<span class="badge ${cls}">${label}</span>`;
  };

  const matchBadge = (real, pred) => {
    return real.toUpperCase() === pred.toUpperCase()
      ? `<span class="badge badge-match">✓ Match</span>`
      : `<span class="badge badge-neg">✗ Diff</span>`;
  };

  const matchCount = rows.filter(r => r.real.toUpperCase() === r.pred.toUpperCase()).length;
  const accuracy = ((matchCount / rows.length) * 100).toFixed(1);

  container.innerHTML = `
    <div style="display:flex;justify-content:between;align-items:center;margin-bottom:16px;color:#94a3b8;font-size:0.8rem;">
      <p>${rows.length} registros</p>
      <span class="badge badge-match" style="margin-left:auto;">Precisión: ${accuracy}% (${matchCount}/${rows.length})</span>
    </div>
    <div style="overflow-x:auto;">
      <table class="ai-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Entidad</th>
            <th>Real</th>
            <th>Predicción</th>
            <th>Match</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r, i) => `
            <tr>
              <td>${i + 1}</td>
              <td style="color:#a5b4fc;font-weight:600;">${r.entity}</td>
              <td>${sentimentBadge(r.real)}</td>
              <td>${sentimentBadge(r.pred)}</td>
              <td>${matchBadge(r.real, r.pred)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// ── Ctrl+Enter shortcut ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('textInput');
  if (ta) {
    ta.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === 'Enter') enviarDatos();
    });
  }
});