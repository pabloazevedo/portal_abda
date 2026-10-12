// ══════════════════════════════════════════════════════════════
// Portal — app.js
// ══════════════════════════════════════════════════════════════

// ── Sidebar mobile toggle ────────────────────────────────────
const sidebar   = document.getElementById('sidebar');
const overlay   = document.getElementById('sidebar-overlay');
const toggleBtn = document.getElementById('sidebar-toggle');

if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  });
}
if (overlay) {
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
  });
}

// ── Toast feedback ───────────────────────────────────────────
function showToast(message, variant) {
  const root = document.getElementById('toast-root');
  if (!root || !message) return;
  const el = document.createElement('div');
  el.className = 'portal-toast ' + (variant || 'success');
  el.setAttribute('role', 'status');
  const icons = { success: 'bi-check-circle-fill', warning: 'bi-exclamation-triangle-fill', danger: 'bi-x-circle-fill' };
  const icon = icons[variant] || icons.success;
  el.innerHTML = '<i class="bi ' + icon + '" aria-hidden="true"></i><span></span>';
  el.querySelector('span').textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity .25s';
    setTimeout(() => el.remove(), 280);
  }, 4500);
}
window.showToast = showToast;

// ── Modal de confirmação (substitui confirm() nativo) ────────
function confirmAction(message, formId, variant) {
  const modalEl = document.getElementById('confirmModal');
  if (!modalEl) {
    if (confirm(message)) document.getElementById(formId).submit();
    return;
  }

  const d = modalEl.dataset;
  const VARIANTS = {
    danger:  {
      title: d.i18nTitleDanger || 'Confirmar exclusão',
      icon: 'bi-trash',
      btnText: d.i18nBtnDanger || 'Excluir',
      cls: 'btn btn-danger'
    },
    warning: {
      title: d.i18nTitleWarning || 'Confirmar inativação',
      icon: 'bi-pause-circle',
      btnText: d.i18nBtnWarning || 'Inativar',
      cls: 'btn btn-warning'
    },
    success: {
      title: d.i18nTitleSuccess || 'Confirmar reativação',
      icon: 'bi-play-circle',
      btnText: d.i18nBtnSuccess || 'Reativar',
      cls: 'btn btn-success'
    },
  };
  const cfg = VARIANTS[variant] || VARIANTS.danger;

  const titleEl   = document.getElementById('confirmModalLabel');
  const msgEl     = document.getElementById('confirmModalMessage');
  const iconEl    = document.getElementById('confirmModalIcon');
  if (iconEl) iconEl.innerHTML = '<i class="bi ' + cfg.icon + '" aria-hidden="true"></i>';
  const cancelBtn = document.getElementById('confirmModalCancel');
  let   okBtn     = document.getElementById('confirmModalOk');

  titleEl.textContent = cfg.title;
  msgEl.textContent   = message;

  // Troca o botão para remover listeners anteriores
  const newOk = okBtn.cloneNode(true);
  newOk.textContent   = cfg.btnText;
  newOk.className     = cfg.cls;
  newOk.style.cssText = 'border-radius:8px; font-size:14px; font-weight:600;';
  okBtn.replaceWith(newOk);
  okBtn = newOk;

  const bsModal = new bootstrap.Modal(modalEl);

  okBtn.addEventListener('click', () => {
    bsModal.hide();
    const form = document.getElementById(formId);
    if (form) {
      // Mostra spinner no botão que disparou a ação
      const triggerBtn = document.querySelector(`[onclick*="${formId}"]`);
      if (triggerBtn) {
        triggerBtn.disabled = true;
        triggerBtn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
      }
      form.submit();
    }
  }, { once: true });

  // Foca "Cancelar" ao abrir — evita ativação acidental do destrutivo
  modalEl.addEventListener('shown.bs.modal', () => cancelBtn.focus(), { once: true });

  bsModal.show();
}

// ── Auto-dismiss alerts (com pausa no hover) ─────────────────
document.querySelectorAll('.alert-auto-dismiss').forEach(el => {
  function dismiss() {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }

  let timer = setTimeout(dismiss, 3500);

  el.addEventListener('mouseenter', () => clearTimeout(timer));
  el.addEventListener('mouseleave', () => { timer = setTimeout(dismiss, 2000); });
});

// ── Search form: clear button ────────────────────────────────
const clearBtn = document.getElementById('clear-search');
if (clearBtn) {
  clearBtn.addEventListener('click', () => {
    const form = document.getElementById('search-form');
    if (form) {
      form.querySelectorAll('input[type="text"], input[type="search"], select').forEach(el => {
        el.value = '';
      });
      form.submit();
    }
  });
}

// ── Photo preview ────────────────────────────────────────────
const photoInput       = document.getElementById('photo-input');
const photoPreview     = document.getElementById('photo-preview');
const photoPlaceholder = document.getElementById('photo-placeholder');

if (photoInput) {
  photoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (photoPreview)     { photoPreview.src = ev.target.result; photoPreview.style.display = 'block'; }
      if (photoPlaceholder) { photoPlaceholder.style.display = 'none'; }
    };
    reader.readAsDataURL(file);
  });
}

const removePhotoBtn   = document.getElementById('remove-photo-btn');
const removePhotoInput = document.getElementById('remove_photo');
if (removePhotoBtn) {
  removePhotoBtn.addEventListener('click', () => {
    if (photoPreview)     { photoPreview.src = ''; photoPreview.style.display = 'none'; }
    if (photoPlaceholder) { photoPlaceholder.style.display = 'flex'; }
    if (removePhotoInput) { removePhotoInput.value = '1'; }
    removePhotoBtn.style.display = 'none';
  });
}

// ── Role checkboxes — visual feedback + campos condicionais ──
(function initRoleCheckboxes() {
  const maestroCheckbox  = document.getElementById('role-maestro');
  const cantorCheckbox   = document.getElementById('role-cantor');
  const maestroGroup     = document.getElementById('maestro-order-group');
  const voiceGroup       = document.getElementById('voice-type-group');

  // Visual feedback: borda/fundo ao marcar qualquer papel
  document.querySelectorAll('.role-check-item').forEach(label => {
    const cb = label.querySelector('input[type="checkbox"]');
    if (!cb) return;
    if (cb.checked) label.classList.add('checked');
    cb.addEventListener('change', () => label.classList.toggle('checked', cb.checked));
  });

  function toggleMaestroOrder() {
    if (!maestroCheckbox || !maestroGroup) return;
    const show = maestroCheckbox.checked;
    maestroGroup.style.display = show ? 'block' : 'none';
    const sel = maestroGroup.querySelector('select');
    if (sel) sel.required = show;
  }

  function toggleVoiceType() {
    if (!cantorCheckbox || !voiceGroup) return;
    const show = cantorCheckbox.checked;
    voiceGroup.style.display = show ? 'block' : 'none';
    const sel = voiceGroup.querySelector('select');
    if (sel) sel.required = show;
  }

  if (maestroCheckbox) maestroCheckbox.addEventListener('change', toggleMaestroOrder);
  if (cantorCheckbox)  cantorCheckbox.addEventListener('change', toggleVoiceType);

  toggleMaestroOrder();
  toggleVoiceType();
})();

// ── Typeahead — busca de instrumentos ───────────────────────
(function initTypeahead() {
  const input           = document.getElementById('instrument-search');
  const dropdown        = document.getElementById('instrument-dropdown');
  const tagsContainer   = document.getElementById('instrument-tags');
  const hiddenContainer = document.getElementById('instrument-hidden-inputs');

  if (!input || !dropdown || !tagsContainer || !hiddenContainer) return;

  // Spinner inserido dinamicamente ao lado do input
  const spinnerEl = document.createElement('span');
  spinnerEl.className = 'typeahead-spin-icon';
  spinnerEl.setAttribute('aria-hidden', 'true');
  spinnerEl.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
  input.after(spinnerEl);

  const selectedIds = new Set(
    Array.from(hiddenContainer.querySelectorAll('input[name="instrumento_ids"]'))
         .map(el => el.value)
  );

  let debounceTimer = null;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fetchInstruments(input.value.trim()), 200);
  });

  input.addEventListener('focus', () => fetchInstruments(input.value.trim()));

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.typeahead-wrapper')) dropdown.style.display = 'none';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { dropdown.style.display = 'none'; input.blur(); }
    if (e.key === 'ArrowDown') {
      const first = dropdown.querySelector('.typeahead-item');
      if (first) { first.focus(); e.preventDefault(); }
    }
  });

  dropdown.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      const next = e.target.nextElementSibling;
      if (next && next.classList.contains('typeahead-item')) { next.focus(); e.preventDefault(); }
    }
    if (e.key === 'ArrowUp') {
      const prev = e.target.previousElementSibling;
      if (prev && prev.classList.contains('typeahead-item')) { prev.focus(); e.preventDefault(); }
      else input.focus();
      e.preventDefault();
    }
    if (e.key === 'Enter' && e.target.classList.contains('typeahead-item')) {
      e.target.click(); e.preventDefault();
    }
    if (e.key === 'Escape') { dropdown.style.display = 'none'; input.focus(); }
  });

  async function fetchInstruments(q) {
    spinnerEl.classList.add('visible');
    try {
      const url  = `/instrumentos/search?q=${encodeURIComponent(q)}&limit=14`;
      const resp = await fetch(url);
      if (!resp.ok) return;
      const items = await resp.json();
      renderDropdown(items);
    } catch (_) {
      // ignora erros de rede silenciosamente
    } finally {
      spinnerEl.classList.remove('visible');
    }
  }

  function renderDropdown(items) {
    dropdown.innerHTML = '';
    if (items.length === 0) { dropdown.style.display = 'none'; return; }

    let currentCategory = null;
    items.forEach(item => {
      if (item.categoria !== currentCategory) {
        currentCategory = item.categoria;
        const header = document.createElement('div');
        header.className   = 'typeahead-category';
        header.textContent = currentCategory;
        dropdown.appendChild(header);
      }
      const el = document.createElement('div');
      el.className       = 'typeahead-item';
      el.textContent     = item.nome;
      el.tabIndex        = 0;
      el.dataset.id      = String(item.id);
      el.dataset.nome    = item.nome;
      if (selectedIds.has(String(item.id))) el.classList.add('selected');
      el.addEventListener('click', () => selectInstrument(item));
      dropdown.appendChild(el);
    });
    dropdown.style.display = 'block';
  }

  function selectInstrument(item) {
    const idStr = String(item.id);
    if (selectedIds.has(idStr)) { dropdown.style.display = 'none'; input.value = ''; return; }

    selectedIds.add(idStr);

    const hidden   = document.createElement('input');
    hidden.type    = 'hidden';
    hidden.name    = 'instrumento_ids';
    hidden.value   = idStr;
    hidden.id      = `hidden-inst-${idStr}`;
    hiddenContainer.appendChild(hidden);

    const tag        = document.createElement('span');
    tag.className    = 'instrument-tag-edit';
    tag.dataset.id   = idStr;
    tag.innerHTML    = `${escapeHtml(item.nome)} <button type="button" aria-label="Remover ${escapeHtml(item.nome)}">&times;</button>`;
    tag.querySelector('button').addEventListener('click', () => removeInstrument(idStr));
    tagsContainer.appendChild(tag);

    input.value = '';
    dropdown.style.display = 'none';
    input.focus();
  }

  window.removeInstrument = function(idStr) {
    idStr = String(idStr);
    selectedIds.delete(idStr);
    const hidden = document.getElementById(`hidden-inst-${idStr}`);
    if (hidden) hidden.remove();
    const tag = tagsContainer.querySelector(`[data-id="${idStr}"]`);
    if (tag) tag.remove();
  };

  function escapeHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
})();

// ── Máscara de telefone (IMask) ──────────────────────────────
(function initPhoneMask() {
  if (typeof IMask === 'undefined') return;

  document.querySelectorAll('input[name="celular"], input[name="telefone"]').forEach(el => {
    IMask(el, {
      mask: [
        { mask: '(00) 0000-0000' },
        { mask: '(00) 00000-0000' },
      ],
      dispatch(appended, dynamicMasked) {
        const digits = (dynamicMasked.value + appended).replace(/\D/g, '');
        return dynamicMasked.compiledMasks[digits.length > 10 ? 1 : 0];
      },
    });
  });
})();

// ── Validação em tempo real (blur) ───────────────────────────
(function initRealtimeValidation() {
  // Email
  document.querySelectorAll('input[type="email"]').forEach(el => {
    function validate() {
      if (!el.value) { el.classList.remove('is-valid', 'is-invalid'); return; }
      const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value);
      el.classList.toggle('is-valid', valid);
      el.classList.toggle('is-invalid', !valid);
    }
    el.addEventListener('blur', validate);
    el.addEventListener('input', () => {
      if (el.classList.contains('is-valid') || el.classList.contains('is-invalid')) validate();
    });
  });

  // Telefone / celular
  document.querySelectorAll('input[name="celular"], input[name="telefone"]').forEach(el => {
    el.addEventListener('blur', () => {
      if (!el.value) { el.classList.remove('is-valid', 'is-invalid'); return; }
      const digits = el.value.replace(/\D/g, '');
      const valid  = digits.length >= 10;
      el.classList.toggle('is-valid', valid);
      el.classList.toggle('is-invalid', !valid);
    });
  });
})();

// ── Proteção contra navegação com dados não salvos ───────────
(function initFormGuard() {
  const form = document.querySelector('form[data-guard]');
  if (!form) return;

  let dirty = false;
  form.addEventListener('input', () => { dirty = true; });
  form.addEventListener('submit', () => { dirty = false; });

  window.addEventListener('beforeunload', (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  // Intercepta apenas links marcados para saída do formulário
  document.querySelectorAll('a[data-guard-leave]').forEach(link => {
    link.addEventListener('click', (e) => {
      if (!dirty) return;
      const modalEl = document.getElementById('confirmModal');
      const msg = (modalEl && modalEl.dataset.i18nUnsaved)
        || 'Você tem alterações não salvas. Deseja sair mesmo assim?';
      if (!confirm(msg)) e.preventDefault();
      else dirty = false;
    });
  });
})();

// ── Atalhos de teclado globais ───────────────────────────────
document.addEventListener('keydown', (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (!mod) return;

  // Ctrl+K → foca busca global (topbar) ou busca local da página
  if (e.key === 'k') {
    const globalSearch = document.getElementById('global-search');
    const localSearch  = document.querySelector('input[name="search"], input[name="q"], #instrument-search');
    const target = globalSearch || localSearch;
    if (target) { e.preventDefault(); target.focus(); target.select(); }
  }

  // Ctrl+N → novo músico ou novo patrimônio conforme página atual
  if (e.key === 'n') {
    const path = window.location.pathname;
    if (path.startsWith('/musicians')) {
      e.preventDefault(); window.location.href = '/musicians/new';
    } else if (path.startsWith('/patrimonio')) {
      e.preventDefault(); window.location.href = '/patrimonio/new';
    }
  }
});

// ── Dark mode (3 estados: light → dark → system) ─────────────
(function initDarkMode() {
  const html   = document.documentElement;
  const btn    = document.getElementById('dark-mode-toggle');
  const icon   = document.getElementById('dark-mode-icon');
  const CYCLE  = ['light', 'dark', 'system'];
  const ICONS  = { light: 'bi bi-sun-fill', dark: 'bi bi-moon-fill', system: 'bi bi-circle-half' };
  const LABELS = {
    light: (btn && btn.dataset.labelLight) || 'Claro',
    dark: (btn && btn.dataset.labelDark) || 'Escuro',
    system: (btn && btn.dataset.labelSystem) || 'Padrão do Sistema',
  };
  const PREFIX = (btn && btn.dataset.labelPrefix) || 'Tema';

  function systemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    const effective = theme === 'system' ? systemTheme() : theme;
    html.setAttribute('data-theme',    effective);
    html.setAttribute('data-bs-theme', effective);
    if (icon) icon.className = ICONS[theme];
    if (btn) {
      btn.title = PREFIX + ': ' + LABELS[theme];
      btn.setAttribute('aria-label', PREFIX + ': ' + LABELS[theme]);
    }
    localStorage.setItem('portal-theme', theme);
    const live = document.getElementById('theme-live');
    if (live) live.textContent = PREFIX + ': ' + LABELS[theme];
  }

  const saved = localStorage.getItem('portal-theme') || 'system';
  applyTheme(saved);

  // Atualiza automaticamente se o tema do SO mudar e o modo for "system"
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem('portal-theme') || 'system') === 'system') applyTheme('system');
  });

  if (btn) {
    btn.addEventListener('click', () => {
      const current = localStorage.getItem('portal-theme') || 'system';
      const next    = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
      applyTheme(next);
    });
  }
})();

// ── Busca global (topbar) ────────────────────────────────────
(function initGlobalSearch() {
  const input    = document.getElementById('global-search');
  const dropdown = document.getElementById('global-search-dropdown');
  const spinner  = document.getElementById('global-search-spinner');
  if (!input || !dropdown) return;

  let debounceTimer = null;
  let lastQuery     = '';

  const show = () => { dropdown.hidden = false; input.setAttribute('aria-expanded', 'true');  };
  const hide = () => { dropdown.hidden = true;  input.setAttribute('aria-expanded', 'false'); };

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) { hide(); return; }
    debounceTimer = setTimeout(() => fetchResults(q), 300);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { hide(); input.blur(); return; }
    if (e.key === 'ArrowDown') {
      const first = dropdown.querySelector('[role="option"]');
      if (first) { first.focus(); e.preventDefault(); }
    }
  });

  dropdown.addEventListener('keydown', (e) => {
    const items = Array.from(dropdown.querySelectorAll('[role="option"]'));
    const idx   = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') {
      if (idx < items.length - 1) items[idx + 1].focus();
      e.preventDefault();
    }
    if (e.key === 'ArrowUp') {
      if (idx > 0) items[idx - 1].focus(); else input.focus();
      e.preventDefault();
    }
    if (e.key === 'Escape')  { hide(); input.focus(); }
    if (e.key === 'Enter' && document.activeElement.tagName === 'A') {
      document.activeElement.click();
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('#topbar-search-container')) hide();
  });

  async function fetchResults(q) {
    if (q === lastQuery) return;
    lastQuery = q;
    if (spinner) spinner.classList.add('visible');
    try {
      const res  = await fetch(`/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) return;
      const data = await res.json();
      render(data, q);
    } catch (_) {
      hide();
    } finally {
      if (spinner) spinner.classList.remove('visible');
    }
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function hl(text, q) {
    const safe = esc(text);
    const re   = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`, 'gi');
    return safe.replace(re, '<mark style="background:rgba(107,132,255,0.2);color:inherit;border-radius:2px;padding:0 1px;">$1</mark>');
  }

  function render(data, q) {
    dropdown.innerHTML = '';
    const musicians  = data.musicians  || [];
    const patrimonio = data.patrimonio || [];
    const obras      = data.obras      || [];
    const hasM = musicians.length  > 0;
    const hasP = patrimonio.length > 0;
    const hasO = obras.length      > 0;

    if (!hasM && !hasP && !hasO) {
      dropdown.innerHTML = `<div class="search-empty">
        <i class="bi bi-search" style="font-size:22px;opacity:.25;display:block;margin-bottom:8px;" aria-hidden="true"></i>
        Nenhum resultado para <strong>${esc(q)}</strong></div>`;
      show(); return;
    }

    if (hasM) {
      const hdr = document.createElement('div');
      hdr.className   = 'search-section-title';
      hdr.textContent = `Membros (${musicians.length})`;
      dropdown.appendChild(hdr);

      musicians.forEach(m => {
        const a       = document.createElement('a');
        a.href        = m.url;
        a.className   = 'search-result-item';
        a.setAttribute('role', 'option');
        a.tabIndex    = 0;
        a.innerHTML   = `
          <div class="search-result-icon person" aria-hidden="true"><i class="bi bi-person-fill"></i></div>
          <div style="min-width:0;">
            <div class="search-result-name">${hl(m.name, q)}</div>
            <div class="search-result-sub">${esc(m.email)}</div>
          </div>
          ${!m.is_active ? '<span class="badge-type badge-inactive ms-auto" style="font-size:9px;white-space:nowrap;">Inativo</span>' : ''}`;
        a.addEventListener('click', hide);
        dropdown.appendChild(a);
      });
    }

    if (hasP) {
      const hdr = document.createElement('div');
      hdr.className   = 'search-section-title';
      hdr.textContent = `Inventário (${patrimonio.length})`;
      dropdown.appendChild(hdr);

      patrimonio.forEach(p => {
        const sub = [p.fabricante, p.modelo].filter(Boolean).join(' · ') || p.tipo;
        const a   = document.createElement('a');
        a.href      = p.url;
        a.className = 'search-result-item';
        a.setAttribute('role', 'option');
        a.tabIndex  = 0;
        a.innerHTML = `
          <div class="search-result-icon item" aria-hidden="true"><i class="bi bi-archive-fill"></i></div>
          <div style="min-width:0;">
            <div class="search-result-name">${hl(p.identificador, q)}</div>
            <div class="search-result-sub">${esc(sub)}</div>
          </div>`;
        a.addEventListener('click', hide);
        dropdown.appendChild(a);
      });
    }

    if (hasO) {
      const hdr = document.createElement('div');
      hdr.className   = 'search-section-title';
      hdr.textContent = `Obras (${obras.length})`;
      dropdown.appendChild(hdr);

      obras.forEach(o => {
        const a       = document.createElement('a');
        a.href        = o.url;
        a.className   = 'search-result-item';
        a.setAttribute('role', 'option');
        a.tabIndex    = 0;
        a.innerHTML   = `
          <div class="search-result-icon item" aria-hidden="true"><i class="bi bi-music-note-beamed"></i></div>
          <div style="min-width:0;">
            <div class="search-result-name">${hl(o.titulo, q)}</div>
            <div class="search-result-sub">${esc(o.compositor || '')}</div>
          </div>`;
        a.addEventListener('click', hide);
        dropdown.appendChild(a);
      });
    }

    show();
  }
})();
