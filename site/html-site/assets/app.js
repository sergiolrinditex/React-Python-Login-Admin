// ===================================================================
// Orquestador DAG — interactividad ligera, zero deps
// ===================================================================

(function () {
  'use strict';

  // -----------------------------------------------------------------
  // 1. Auto-mark current nav item
  // -----------------------------------------------------------------
  const here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  document.querySelectorAll('.topnav a').forEach(a => {
    const href = (a.getAttribute('href') || '').toLowerCase();
    if (href === here || (here === '' && href === 'index.html')) {
      a.setAttribute('aria-current', 'page');
      a.classList.add('active');
    }
  });

  // -----------------------------------------------------------------
  // 2. Fade-in observer for cards/sections
  // -----------------------------------------------------------------
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('fade-in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.card, .panel, .kpi-card, .step').forEach(el => io.observe(el));
  }

  // -----------------------------------------------------------------
  // 3. Calculator (negocio.html)
  // -----------------------------------------------------------------
  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function calcSavings() {
    const tasks = Number(document.getElementById('tasks')?.value || 84);
    const waves = Number(document.getElementById('waves')?.value || 8);
    const terms = Number(document.getElementById('terms')?.value || 3);
    const conflict = Number(document.getElementById('conflict')?.value || 35) / 100;
    const human = Number(document.getElementById('human')?.value || 20) / 100;

    const theoretical = tasks / Math.max(waves, 1);
    let practical = Math.min(theoretical, terms) * (1 - conflict) * (1 - human);
    if (practical < 1) practical = 1;

    setText('tasksOut', tasks);
    setText('wavesOut', waves);
    setText('termsOut', terms);
    setText('conflictOut', Math.round(conflict * 100) + '%');
    setText('humanOut', Math.round(human * 100) + '%');
    setText('speedOut', practical.toFixed(1) + 'x');
    setText('saveOut', Math.max(0, Math.round((1 - 1 / practical) * 100)) + '%');
  }

  ['tasks', 'waves', 'terms', 'conflict', 'human'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', calcSavings);
  });

  if (document.getElementById('tasks')) calcSavings();

  // -----------------------------------------------------------------
  // 4. DAG simulator (flujo-dag.html)
  // -----------------------------------------------------------------
  const dagState = { A: false, B: false };

  function applyDagState() {
    const a = document.getElementById('node-a');
    const b = document.getElementById('node-b');
    const j = document.getElementById('node-join');
    const log = document.getElementById('sim-log');
    const edgeAJ = document.getElementById('edge-a-j');
    const edgeBJ = document.getElementById('edge-b-j');
    if (!a) return;

    a.setAttribute('class', 'dag-node ' + (dagState.A ? 'done' : 'ready'));
    b.setAttribute('class', 'dag-node ' + (dagState.B ? 'done' : 'ready'));

    const joinReady = dagState.A && dagState.B;
    j.setAttribute('class', 'dag-node ' + (joinReady ? 'ready' : 'blocked'));

    if (edgeAJ) edgeAJ.setAttribute('class', 'dag-edge ' + (dagState.A ? 'active' : ''));
    if (edgeBJ) edgeBJ.setAttribute('class', 'dag-edge ' + (dagState.B ? 'active' : ''));

    if (log) {
      log.className = 'notice ' + (joinReady ? 'success' : 'warning');
      log.innerHTML = joinReady
        ? '<strong>Join listo.</strong> <code>/next-wave</code> ya puede proponer <code>P00-S02-T001</code>.'
        : '<strong>Join bloqueado.</strong> <code>claim_task.py</code> deniega hasta que ambos predecessors estén <code>done</code>.';
    }
  }

  window.dagDoneA = function () { dagState.A = true; applyDagState(); };
  window.dagDoneB = function () { dagState.B = true; applyDagState(); };
  window.dagReset = function () { dagState.A = false; dagState.B = false; applyDagState(); };

  if (document.getElementById('node-a')) applyDagState();

  // -----------------------------------------------------------------
  // 5. Toggle helper (kept for compatibility)
  // -----------------------------------------------------------------
  window.toggle = function (id) {
    const el = document.getElementById(id);
    if (el) el.hidden = !el.hidden;
  };

  // -----------------------------------------------------------------
  // 6. Copy-to-clipboard for <pre> blocks with [data-copy]
  // -----------------------------------------------------------------
  document.querySelectorAll('pre[data-copy]').forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'btn copy-btn';
    btn.type = 'button';
    btn.style.position = 'absolute';
    btn.style.top = '12px';
    btn.style.right = '12px';
    btn.style.padding = '4px 10px';
    btn.style.fontSize = '12px';
    btn.textContent = 'Copy';
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code') || pre;
      const text = code.textContent;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          btn.textContent = 'Copied!';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
        });
      }
    });
    pre.style.position = 'relative';
    pre.appendChild(btn);
  });
})();
