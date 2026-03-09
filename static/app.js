/* ═══════════════════════════════════════════════════════════════
   app.js — RecruitAI main application logic
   Handles: tabs, file upload/remove, analysis, certificates,
            dashboard, toasts, confetti, CSV export
   ═══════════════════════════════════════════════════════════════ */

/* ─── STATE ─── */
let selectedFiles = [];      // Array of File objects for resume upload
let lastResults   = [];      // Last batch analysis results
let allResults    = [];      // Cumulative results across all analyses
let totalResumes  = 0;
let totalCerts    = 0;

/* ═══════════════════════════════════════════
   TOAST SYSTEM
   ═══════════════════════════════════════════ */
function showToast(message, type = 'success') {
  const box = document.getElementById('toastBox');
  const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
  const id = 't_' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = 'toast toast-' + type;
  el.innerHTML = `<i class="fas fa-${icons[type] || icons.info}"></i><span>${message}</span><button onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>`;
  box.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 3500);
}

/* ═══════════════════════════════════════════
   TAB NAVIGATION
   ═══════════════════════════════════════════ */
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('pane-' + tab.dataset.tab).classList.add('active');
    // Load dashboard data when switching to dash tab
    if (tab.dataset.tab === 'dash') loadDashboard();
    // Check blockchain when switching to cert tab
    if (tab.dataset.tab === 'cert') { checkBlockchain(); populateCandidateDropdown(); }
  });
});

/* Mobile burger */
const burger = document.getElementById('navBurger');
if (burger) {
  burger.addEventListener('click', () => {
    document.getElementById('navTabs').classList.toggle('open');
  });
}

/* ═══════════════════════════════════════════
   LOGOUT
   ═══════════════════════════════════════════ */
async function doLogout() {
  try {
    await fetch('/logout', { method: 'POST' });
  } catch (e) { /* ignore */ }
  window.location.href = '/auth';
}

/* ═══════════════════════════════════════════
   JOB DESCRIPTION
   ═══════════════════════════════════════════ */
const jdEl = document.getElementById('jobDesc');
const jdCount = document.getElementById('jdCount');
if (jdEl) {
  jdEl.addEventListener('input', () => {
    jdCount.textContent = jdEl.value.length + ' characters';
    updateAnalyzeBtn();
  });
}

function appendSkill(skill) {
  if (!jdEl) return;
  const sep = jdEl.value.trim() ? ', ' : '';
  jdEl.value += sep + skill;
  jdEl.dispatchEvent(new Event('input'));
  showToast(skill + ' added', 'info');
}

/* ═══════════════════════════════════════════
   FILE UPLOAD + REMOVE (Resume Tab)
   Uses a JS array (selectedFiles) instead of
   relying on the native FileList, enabling
   individual file removal.
   ═══════════════════════════════════════════ */
const dropZone  = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const chipsEl    = document.getElementById('fileChips');
const badgeEl    = document.getElementById('fileBadge');
const clearBtn   = document.getElementById('btnClearAll');

if (dropZone) {
  dropZone.addEventListener('click', (e) => {
    // Only trigger file picker if clicking the zone itself, not the native input
    if (e.target !== fileInput) fileInput.click();
  });
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });
}

function addFiles(fileList) {
  for (const f of fileList) {
    if (f.type !== 'application/pdf') {
      showToast(f.name + ' is not a PDF — skipped', 'error');
      if (dropZone) { dropZone.classList.add('shake'); setTimeout(() => dropZone.classList.remove('shake'), 500); }
      continue;
    }
    if (selectedFiles.length >= 10) { showToast('Maximum 10 files allowed', 'error'); break; }
    // Prevent duplicates by name
    if (!selectedFiles.some(sf => sf.name === f.name && sf.size === f.size)) {
      selectedFiles.push(f);
    }
  }
  renderChips();
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderChips();
  showToast('File removed', 'info');
}

function clearAllFiles() {
  selectedFiles = [];
  renderChips();
  showToast('All files cleared', 'info');
}

function renderChips() {
  if (!chipsEl) return;
  if (!selectedFiles.length) {
    chipsEl.innerHTML = '';
    badgeEl.style.display = 'none';
    clearBtn.style.display = 'none';
    updateAnalyzeBtn();
    return;
  }
  let html = '';
  selectedFiles.forEach((f, i) => {
    const size = (f.size / 1024).toFixed(0);
    html += `<div class="file-chip">
      <i class="fas fa-file-pdf"></i>
      <span class="fc-name" title="${f.name}">${truncate(f.name, 28)}</span>
      <span class="fc-size">${size} KB</span>
      <button class="fc-remove" onclick="removeFile(${i})" title="Remove file"><i class="fas fa-times"></i></button>
    </div>`;
  });
  chipsEl.innerHTML = html;
  badgeEl.textContent = selectedFiles.length + ' PDF' + (selectedFiles.length > 1 ? 's' : '');
  badgeEl.style.display = 'inline-flex';
  clearBtn.style.display = selectedFiles.length >= 2 ? 'inline-flex' : 'none';
  updateAnalyzeBtn();
}

function truncate(s, n) { return s.length > n ? s.slice(0, n - 3) + '…' : s; }

function updateAnalyzeBtn() {
  const btn = document.getElementById('btnAnalyze');
  if (btn) btn.disabled = !(selectedFiles.length > 0 && jdEl && jdEl.value.trim().length > 0);
}

/* ═══════════════════════════════════════════
   ANALYZE RESUMES
   ═══════════════════════════════════════════ */
async function analyzeResumes() {
  const btn   = document.getElementById('btnAnalyze');
  const label = btn.querySelector('.btn-label');
  const load  = btn.querySelector('.btn-loading');

  btn.disabled = true;
  label.style.display = 'none';
  load.style.display  = 'inline-flex';

  const fd = new FormData();
  fd.append('job_description', jdEl.value);
  selectedFiles.forEach(f => fd.append('resumes', f));

  try {
    const res  = await fetch('/upload-resume', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }

    lastResults = data.results;
    allResults = data.all_results || allResults.concat(data.results);
    totalResumes = allResults.length;
    renderResultCards(lastResults);
    populateCandidateDropdown();
    document.getElementById('resultsArea').style.display = 'block';
    showToast(`Ranked ${lastResults.length} resume(s) successfully! (${allResults.length} total)`);

    // Confetti for top result
    if (lastResults.length > 0) launchConfetti();
  } catch (err) {
    showToast('Server error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    label.style.display = 'inline-flex';
    load.style.display  = 'none';
  }
}

function reAnalyze() {
  document.getElementById('resultsArea').style.display = 'none';
  analyzeResumes();
}

/* ═══════════════════════════════════════════
   RENDER RESULT CARDS
   ═══════════════════════════════════════════ */
function renderResultCards(results) {
  const grid = document.getElementById('resultsGrid');
  grid.innerHTML = '';
  results.forEach((r, i) => {
    const pct  = r.score;
    const circumference = 2 * Math.PI * 38;
    const offset = circumference - (pct / 100) * circumference;
    const color = pct >= 70 ? '#00d4aa' : pct >= 40 ? '#f5a623' : '#ff4d4d';
    const label = pct >= 70 ? 'Excellent' : pct >= 40 ? 'Good' : pct >= 20 ? 'Average' : 'Poor';
    const labelCls = pct >= 70 ? 'lbl-green' : pct >= 40 ? 'lbl-amber' : 'lbl-red';
    const isTop = r.rank === 1;

    const card = document.createElement('div');
    card.className = 'result-card' + (isTop ? ' top-card' : '');
    card.style.animationDelay = (i * 0.08) + 's';
    card.innerHTML = `
      <div class="rc-rank">${r.rank}</div>
      <div class="rc-info">
        <h4 class="rc-name">${r.filename}</h4>
        <span class="rc-label ${labelCls}">${label} Match</span>
        ${isTop ? '<span class="rc-badge">⭐ Top Match</span>' : ''}
      </div>
      <div class="rc-ring">
        <svg viewBox="0 0 88 88">
          <circle cx="44" cy="44" r="38" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="6"/>
          <circle cx="44" cy="44" r="38" fill="none" stroke="${color}" stroke-width="6"
            stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"
            stroke-linecap="round" transform="rotate(-90 44 44)" class="ring-progress"
            style="--target:${offset}"/>
        </svg>
        <span class="rc-pct">${pct}%</span>
      </div>`;
    grid.appendChild(card);
  });
  // Trigger ring animation after render
  requestAnimationFrame(() => {
    document.querySelectorAll('.ring-progress').forEach(c => {
      c.style.strokeDashoffset = c.style.getPropertyValue('--target');
    });
  });
}

/* ═══════════════════════════════════════════
   CERTIFICATE UPLOAD / REMOVE
   ═══════════════════════════════════════════ */
function handleCertFile(type) {
  const input   = document.getElementById(type + 'FileInput');
  const zone    = document.getElementById(type + 'UploadZone');
  const preview = document.getElementById(type + 'FilePreview');
  const nameEl  = document.getElementById(type + 'FileName');
  if (input.files.length) {
    zone.style.display    = 'none';
    preview.style.display = 'flex';
    nameEl.textContent    = truncate(input.files[0].name, 32);
  }
}

function removeCertFile(type) {
  const input   = document.getElementById(type + 'FileInput');
  const zone    = document.getElementById(type + 'UploadZone');
  const preview = document.getElementById(type + 'FilePreview');
  input.value = '';
  zone.style.display    = 'block';
  preview.style.display = 'none';
  document.getElementById(type + 'Result').innerHTML = '';
  showToast('File removed', 'info');
}

/* ═══════════════════════════════════════════
   STORE CERTIFICATE
   ═══════════════════════════════════════════ */
function getCandidateDropdown() {
  return document.getElementById('certCandidate');
}

function populateCandidateDropdown() {
  const sel = getCandidateDropdown();
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">— Select a candidate —</option>';
  allResults.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.filename;
    opt.textContent = `#${r.rank} ${r.filename} (${r.score}%)`;
    if (r.cert_status === 'verified') opt.textContent += ' ✅';
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

async function storeCert() {
  const input = document.getElementById('storeFileInput');
  if (!input.files.length) { showToast('Select a certificate file first', 'error'); return; }
  const candidate = getCandidateDropdown()?.value || '';
  if (!candidate) { showToast('Select a candidate first', 'error'); return; }
  const fd = new FormData();
  fd.append('certificate', input.files[0]);
  fd.append('candidate', candidate);
  try {
    const res  = await fetch('/store-certificate', { method: 'POST', body: fd });
    const data = await res.json();
    const div  = document.getElementById('storeResult');
    if (data.error) { div.innerHTML = errBadge(data.error); showToast(data.error, 'error'); return; }
    div.innerHTML = `
      <div class="cert-ok"><i class="fas fa-check-circle"></i> ${data.status}</div>
      <div class="hash-box">
        <label>SHA-256 Hash</label>
        <div class="hash-copy"><code>${data.hash}</code><button onclick="copyHash(this,'${data.hash}')"><i class="fas fa-copy"></i></button></div>
      </div>
      <div class="hash-box">
        <label>Transaction Hash</label>
        <div class="hash-copy"><code>${data.tx_hash}</code><button onclick="copyHash(this,'${data.tx_hash}')"><i class="fas fa-copy"></i></button></div>
      </div>`;
    showToast('Certificate stored on blockchain!');
  } catch (err) { showToast('Error: ' + err.message, 'error'); }
}

/* ═══════════════════════════════════════════
   VERIFY CERTIFICATE
   ═══════════════════════════════════════════ */
async function verifyCert() {
  const input = document.getElementById('verifyFileInput');
  if (!input.files.length) { showToast('Select a certificate file first', 'error'); return; }
  const candidate = getCandidateDropdown()?.value || '';
  if (!candidate) { showToast('Select a candidate first', 'error'); return; }
  const fd = new FormData();
  fd.append('certificate', input.files[0]);
  fd.append('candidate', candidate);
  try {
    const res  = await fetch('/verify-certificate', { method: 'POST', body: fd });
    const data = await res.json();
    const div  = document.getElementById('verifyResult');
    if (data.error) { div.innerHTML = errBadge(data.error); showToast(data.error, 'error'); return; }

    const ok       = data.status === 'Verified';
    const mismatch = data.status === 'Mismatch';
    const notFound = !ok && !mismatch;

    if (ok) {
      totalCerts++;
      // Update local allResults with verified status
      const cand = data.candidate || '';
      if (cand) {
        allResults.forEach(r => {
          if (r.filename === cand) { r.cert_status = 'verified'; r.cert_hash = data.hash; }
        });
      }
      populateCandidateDropdown();
    }

    // Show overlay modal
    const overlay = document.getElementById('verifyOverlay');
    const modal   = document.getElementById('verifyModal');

    let iconClass, icon, heading, headClass, subText;
    if (ok) {
      iconClass = 'vm-ok';    icon = 'check';            headClass = 'text-green';
      heading = 'VERIFIED';    subText = 'This certificate is authentic and matches this candidate.';
    } else if (mismatch) {
      iconClass = 'vm-warn';   icon = 'exclamation-triangle'; headClass = 'text-amber';
      heading = 'MISMATCH';    subText = data.message || 'This certificate does not belong to this candidate.';
    } else {
      iconClass = 'vm-fail';   icon = 'times';            headClass = 'text-red';
      heading = 'NOT VERIFIED'; subText = 'This certificate hash was not found on the blockchain.';
    }

    modal.innerHTML = `
      <div class="vm-icon ${iconClass}">
        <i class="fas fa-${icon}"></i>
      </div>
      <h2 class="${headClass}">${heading}</h2>
      <p class="vm-sub">${subText}</p>
      <div class="hash-box">
        <label>SHA-256 Hash</label>
        <div class="hash-copy"><code>${data.hash}</code><button onclick="copyHash(this,'${data.hash}')"><i class="fas fa-copy"></i></button></div>
      </div>
      <button class="btn-primary mt-1" onclick="closeVerifyOverlay()">Close</button>`;
    overlay.classList.add('open');
    showToast(ok ? 'Certificate verified!' : mismatch ? 'Certificate mismatch!' : 'Certificate NOT found', ok ? 'success' : 'error');
  } catch (err) { showToast('Error: ' + err.message, 'error'); }
}

function closeVerifyOverlay(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('verifyOverlay').classList.remove('open');
}

function errBadge(msg) {
  // Truncate extremely long error messages to prevent UI crash
  const clean = msg.length > 150 ? msg.slice(0, 150) + '…' : msg;
  return `<div class="cert-fail"><i class="fas fa-exclamation-circle"></i> ${clean}</div>`;
}

/* ═══════════════════════════════════════════
   COPY HASH
   ═══════════════════════════════════════════ */
function copyHash(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const icon = btn.querySelector('i');
    icon.className = 'fas fa-check';
    setTimeout(() => icon.className = 'fas fa-copy', 1500);
    showToast('Copied to clipboard', 'info');
  }).catch(() => showToast('Copy failed', 'error'));
}

/* ═══════════════════════════════════════════
   BLOCKCHAIN STATUS
   ═══════════════════════════════════════════ */
async function checkBlockchain() {
  try {
    const res  = await fetch('/blockchain-status');
    const data = await res.json();
    const dot  = document.getElementById('bcDot');
    const lbl  = document.getElementById('bcLabel');
    if (data.connected) {
      dot.className = 'bc-dot connected';
      lbl.textContent = 'Ganache Connected';
    } else {
      dot.className = 'bc-dot disconnected';
      lbl.textContent = 'Offline Mode — AI features still work';
    }
  } catch {
    document.getElementById('bcDot').className = 'bc-dot disconnected';
    document.getElementById('bcLabel').textContent = 'Offline Mode — AI features still work';
  }
}
checkBlockchain();

/* ═══════════════════════════════════════════
   DASHBOARD
   ═══════════════════════════════════════════ */
async function loadDashboard() {
  try {
    const res  = await fetch('/dashboard-data');
    const data = await res.json();
    if (data.results && data.results.length) {
      allResults   = data.results;
      totalResumes = data.total_resumes || allResults.length;
      totalCerts   = data.total_certs || 0;
    }
  } catch { /* use local state */ }
  renderDashboard();
}

function renderDashboard() {
  // Stats with count-up
  animateCounter('dStatResumes', totalResumes);
  animateCounter('dStatCerts', totalCerts);
  const topScore = allResults.length ? allResults[0].score : 0;
  if (allResults.length) {
    const el = document.getElementById('dStatTop');
    el.textContent = topScore + '%';
  }
  const pending = allResults.length ? Math.max(0, allResults.length - totalCerts) : 0;
  animateCounter('dStatPending', pending);

  // Sparklines
  renderSparkline('spark1', generateSparkData(totalResumes));
  renderSparkline('spark2', generateSparkData(topScore));
  renderSparkline('spark3', generateSparkData(totalCerts));
  renderSparkline('spark4', generateSparkData(pending));

  // Table — show ALL cumulative results, not just last batch
  renderDashTable(allResults);
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  let start = 0;
  const dur = 1200;
  const step = target / (dur / 16);
  if (target === 0) { el.textContent = '0'; return; }
  const timer = setInterval(() => {
    start += step;
    if (start >= target) { start = target; clearInterval(timer); }
    el.textContent = Math.round(start);
  }, 16);
}

function renderSparkline(id, data) {
  const el = document.getElementById(id);
  if (!el) return;
  const max = Math.max(...data, 1);
  const points = data.map((v, i) => `${(i / (data.length - 1)) * 100},${100 - (v / max) * 80}`).join(' ');
  el.innerHTML = `<svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline fill="none" stroke="rgba(0,212,170,.5)" stroke-width="2" points="${points}"/></svg>`;
}

function generateSparkData(seed) {
  const arr = [];
  for (let i = 0; i < 8; i++) arr.push(Math.max(0, seed * (0.3 + Math.random() * 0.7)));
  arr.push(seed);
  return arr;
}

let filteredResults = [];

function renderDashTable(results) {
  filteredResults = [...results];
  applyFilters();
}

function applyFilters() {
  const minScore = parseInt(document.getElementById('filterScore').value);
  document.getElementById('filterScoreVal').textContent = minScore + '%';
  const certFilter = document.getElementById('filterCert').value;

  let filtered = allResults.filter(r => r.score >= minScore);
  if (certFilter === 'verified') filtered = filtered.filter(r => r.cert_status === 'verified');
  if (certFilter === 'pending') filtered = filtered.filter(r => r.cert_status !== 'verified');

  // Always sort descending by score and re-rank
  filtered.sort((a, b) => b.score - a.score);
  filtered.forEach((r, i) => r.rank = i + 1);

  const tbody = document.getElementById('dashBody');
  if (!filtered.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6"><div class="empty-state"><i class="fas fa-inbox"></i><p>No matching results</p><span>Adjust your filters or analyze more resumes.</span></div></td></tr>';
    return;
  }
  let html = '';
  filtered.forEach((r, i) => {
    const pct = r.score;
    const color = pct >= 70 ? '#00d4aa' : pct >= 40 ? '#f5a623' : '#ff4d4d';
    const barW = Math.max(pct, 4);
    html += `<tr style="animation-delay:${i * 0.04}s">
      <td><span class="rank-num">#${r.rank}</span></td>
      <td class="td-name">${r.filename}</td>
      <td>${pct}%</td>
      <td><div class="score-bar-bg"><div class="score-bar-fill" style="width:${barW}%;background:${color}"></div></div></td>
      <td>${r.cert_status === 'verified'
        ? '<span class="pill-badge pill-verified"><i class="fas fa-check-circle"></i> Verified</span>'
        : '<span class="pill-badge pill-pending"><i class="fas fa-hourglass-half"></i> Pending</span>'
      }</td>
      <td class="td-actions">
        <button class="act-btn" title="${r.cert_status === 'verified' ? 'Already Verified' : 'Verify Certificate'}" onclick="switchToCert('${r.filename}')"><i class="fas fa-shield-alt"></i></button>
      </td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function switchToCert(candidateName) {
  document.querySelector('.nav-tab[data-tab="cert"]').click();
  if (candidateName) {
    const sel = getCandidateDropdown();
    if (sel) sel.value = candidateName;
  }
}

/* ═══════════════════════════════════════════
   CSV EXPORT
   ═══════════════════════════════════════════ */
function exportCSV() {
  const data = allResults.length ? allResults : lastResults;
  if (!data.length) { showToast('No data to export', 'info'); return; }
  let csv = 'Rank,Candidate,Match Score (%)\n';
  data.forEach(r => csv += `${r.rank},"${r.filename}",${r.score}\n`);
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'recruitai_results.csv'; a.click();
  URL.revokeObjectURL(url);
  showToast('CSV downloaded!');
}

/* ═══════════════════════════════════════════
   CONFETTI
   ═══════════════════════════════════════════ */
function launchConfetti() {
  const canvas = document.getElementById('confettiCanvas');
  if (!canvas) return;
  canvas.style.display = 'block';
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const pieces = [];
  const colors = ['#00d4aa', '#7c3aed', '#f5a623', '#ff4d4d', '#00b4d8', '#fff'];
  for (let i = 0; i < 120; i++) {
    pieces.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height - canvas.height,
      w: Math.random() * 8 + 4,
      h: Math.random() * 4 + 2,
      color: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 4,
      vy: Math.random() * 4 + 2,
      rot: Math.random() * 360,
      rv: (Math.random() - 0.5) * 8
    });
  }
  let frames = 0;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.rot += p.rv;
      p.vy += 0.05; // gravity
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot * Math.PI / 180);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });
    frames++;
    if (frames < 150) requestAnimationFrame(draw);
    else { ctx.clearRect(0, 0, canvas.width, canvas.height); canvas.style.display = 'none'; }
  }
  draw();
}

/* ═══════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════ */
loadDashboard();
