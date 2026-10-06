(() => {
  const root = document.documentElement;

  // Keep the user's theme choice across role changes and page loads.
  const savedTheme = localStorage.getItem('deptfeedback-theme');
  if (savedTheme === 'dark' || savedTheme === 'light') root.dataset.theme = savedTheme;

  const themeButtons = document.querySelectorAll('[data-theme-toggle]');
  themeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      localStorage.setItem('deptfeedback-theme', next);
      button.setAttribute('aria-label', next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      renderCharts();
    });
  });

  // Responsive drawer navigation.
  const sidebar = document.getElementById('app-sidebar');
  const scrim = document.querySelector('.sidebar-scrim');
  const openSidebar = () => {
    if (!sidebar || !scrim) return;
    sidebar.classList.add('open');
    scrim.classList.add('open');
    document.body.classList.add('drawer-open');
  };
  const closeSidebar = () => {
    if (!sidebar || !scrim) return;
    sidebar.classList.remove('open');
    scrim.classList.remove('open');
    document.body.classList.remove('drawer-open');
  };
  document.querySelectorAll('[data-sidebar-toggle]').forEach((button) => button.addEventListener('click', openSidebar));
  document.querySelectorAll('[data-sidebar-close]').forEach((button) => button.addEventListener('click', closeSidebar));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSidebar(); });

  // Dismissible toast messages with a gentle timeout.
  document.querySelectorAll('.toast').forEach((toast) => {
    const close = toast.querySelector('.toast-close');
    if (close) close.addEventListener('click', () => toast.remove());
    window.setTimeout(() => {
      if (toast.isConnected) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-5px)';
        window.setTimeout(() => toast.remove(), 240);
      }
    }, 6200);
  });

  // Role selection and development-demo shortcuts on the sign-in screen.
  const roleInput = document.querySelector('[data-role-input]');
  const usernameInput = document.querySelector('[data-username-input]');
  const roleLabel = document.querySelector('[data-login-label]');
  const roleOptions = Array.from(document.querySelectorAll('.role-option[data-role]'));
  const roleCopy = {
    student: { label: 'Enrollment number', placeholder: 'e.g. 250183107002' },
    faculty: { label: 'Username or email', placeholder: 'e.g. faculty1' },
    hod: { label: 'HOD username', placeholder: 'Enter your username' },
  };
  const setRole = (role) => {
    if (!roleInput || !roleCopy[role]) return;
    roleInput.value = role;
    if (roleLabel) roleLabel.textContent = roleCopy[role].label;
    if (usernameInput) usernameInput.placeholder = roleCopy[role].placeholder;
    roleOptions.forEach((button) => {
      const active = button.dataset.role === role;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  };
  if (roleInput) setRole(roleInput.value || 'student');
  roleOptions.forEach((button) => button.addEventListener('click', () => setRole(button.dataset.role)));
  document.querySelectorAll('[data-demo-role]').forEach((button) => {
    button.addEventListener('click', () => {
      setRole(button.dataset.demoRole);
      if (usernameInput) usernameInput.value = button.dataset.demoUsername || '';
      const password = document.querySelector('input[name="password"]');
      if (password) password.value = button.dataset.demoPassword || '';
    });
  });
  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = button.parentElement.querySelector('input');
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      button.setAttribute('aria-label', input.type === 'password' ? 'Show password' : 'Hide password');
    });
  });

  // Student feedback form progress, selected radio states, and final confirmation.
  const feedbackForm = document.querySelector('[data-feedback-form]');
  if (feedbackForm) {
    const questions = Array.from(feedbackForm.querySelectorAll('[data-question]'));
    const answeredNode = feedbackForm.querySelector('[data-answered-count]');
    const progress = feedbackForm.querySelector('[data-progress-bar]');
    const updateProgress = () => {
      let answered = 0;
      questions.forEach((question) => {
        const selected = question.querySelector('input[type="radio"]:checked');
        question.querySelectorAll('.rating-choice').forEach((choice) => {
          const radio = choice.querySelector('input');
          choice.classList.toggle('selected', Boolean(radio && radio.checked));
        });
        if (selected) answered += 1;
      });
      if (answeredNode) answeredNode.textContent = String(answered);
      if (progress) progress.style.width = `${questions.length ? (answered / questions.length) * 100 : 0}%`;
    };
    feedbackForm.addEventListener('change', updateProgress);
    updateProgress();
    feedbackForm.addEventListener('submit', (event) => {
      if (!feedbackForm.reportValidity()) return;
      const confirmed = window.confirm('Submit your anonymous feedback now? You will not be able to edit it afterwards.');
      if (!confirmed) event.preventDefault();
    });
  }

  // Filter controls for simple, no-network table views.
  document.querySelectorAll('[data-row-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      const filter = button.dataset.rowFilter;
      const group = button.closest('.panel');
      if (!group) return;
      group.querySelectorAll('[data-row-filter]').forEach((item) => item.classList.toggle('active', item === button));
      group.querySelectorAll('[data-status-row]').forEach((row) => {
        row.hidden = filter !== 'all' && row.dataset.statusRow !== filter;
      });
    });
  });

  // Update selected file name in bulk-import controls.
  document.querySelectorAll('.upload-zone input[type="file"]').forEach((input) => {
    input.addEventListener('change', () => {
      const label = input.closest('.upload-zone');
      const strong = label && label.querySelector('strong');
      if (strong && input.files && input.files[0]) strong.textContent = input.files[0].name;
    });
  });

  // Chart.js is used when available. A tiny canvas renderer keeps charts functional
  // in offline previews where CDN scripts are unavailable.
  const chartInstances = new WeakMap();
  function renderCharts() {
    document.querySelectorAll('canvas[data-chart]').forEach((canvas) => {
      let labels = [];
      let values = [];
      try { labels = JSON.parse(canvas.dataset.chartLabels || '[]'); } catch (_) { labels = []; }
      try { values = JSON.parse(canvas.dataset.chartValues || '[]').map((value) => Number(value) || 0); } catch (_) { values = []; }
      if (window.Chart) {
        const old = chartInstances.get(canvas);
        if (old) old.destroy();
        const style = getComputedStyle(root);
        const textColor = style.getPropertyValue('--muted').trim() || '#778197';
        const gridColor = style.getPropertyValue('--line').trim() || '#e5eaf2';
        const brand = style.getPropertyValue('--brand').trim() || '#5366cc';
        const maxValue = Number(canvas.dataset.chartMax) || undefined;
        const chart = new window.Chart(canvas.getContext('2d'), {
          type: 'bar',
          data: { labels, datasets: [{ data: values, backgroundColor: values.map((_, i) => i === 0 ? '#34a99e' : brand), borderRadius: 5, borderSkipped: false, maxBarThickness: 34 }] },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { displayColors: false, backgroundColor: '#17213a', padding: 10, titleFont: { size: 10 }, bodyFont: { size: 10 } } },
            scales: {
              x: { grid: { display: false }, ticks: { color: textColor, font: { size: 9, family: 'DM Sans, sans-serif' }, maxRotation: 0, autoSkip: false } },
              y: { beginAtZero: true, max: maxValue, grid: { color: gridColor, drawBorder: false }, ticks: { color: textColor, font: { size: 9 }, precision: 0, padding: 6 } },
            },
          },
        });
        chartInstances.set(canvas, chart);
      } else {
        drawFallbackChart(canvas, labels, values);
      }
    });
  }

  function drawFallbackChart(canvas, labels, values) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);
    const context = canvas.getContext('2d');
    context.scale(ratio, ratio);
    const width = rect.width;
    const height = rect.height;
    const style = getComputedStyle(root);
    const textColor = style.getPropertyValue('--muted').trim() || '#778197';
    const gridColor = style.getPropertyValue('--line').trim() || '#e5eaf2';
    const brand = style.getPropertyValue('--brand').trim() || '#5366cc';
    const left = 34, right = 8, top = 12, bottom = 39;
    const chartWidth = Math.max(10, width - left - right);
    const chartHeight = Math.max(10, height - top - bottom);
    const explicitMax = Number(canvas.dataset.chartMax);
    const maxValue = explicitMax > 0 ? explicitMax : Math.max(1, Math.ceil(Math.max(...values, 0) * 1.18));
    context.clearRect(0, 0, width, height);
    context.font = '9px system-ui, sans-serif';
    context.textBaseline = 'middle';
    context.textAlign = 'right';
    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const value = maxValue * i / steps;
      const y = top + chartHeight - chartHeight * i / steps;
      context.strokeStyle = gridColor;
      context.lineWidth = 1;
      context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke();
      context.fillStyle = textColor;
      context.fillText(Number.isInteger(value) ? String(value) : value.toFixed(1), left - 7, y);
    }
    const count = Math.max(labels.length, 1);
    const slot = chartWidth / count;
    const barWidth = Math.min(36, slot * .56);
    values.forEach((value, index) => {
      const x = left + slot * index + (slot - barWidth) / 2;
      const barHeight = chartHeight * Math.max(0, value) / maxValue;
      const y = top + chartHeight - barHeight;
      context.fillStyle = index === 0 ? '#34a99e' : brand;
      const radius = Math.min(5, barWidth / 2);
      context.beginPath();
      context.moveTo(x, y + radius); context.arcTo(x, y, x + barWidth, y, radius); context.arcTo(x + barWidth, y, x + barWidth, y + barHeight, radius); context.lineTo(x + barWidth, top + chartHeight); context.lineTo(x, top + chartHeight); context.closePath(); context.fill();
      const label = String(labels[index] ?? '').length > 13 ? `${String(labels[index]).slice(0, 12)}…` : String(labels[index] ?? '');
      context.fillStyle = textColor; context.textAlign = 'center'; context.textBaseline = 'top';
      context.fillText(label, left + slot * index + slot / 2, top + chartHeight + 8);
    });
  }
  window.addEventListener('resize', renderCharts);
  window.addEventListener('load', renderCharts);
  renderCharts();
})();
