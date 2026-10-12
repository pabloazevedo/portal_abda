/**
 * Portal PWA client — Bearer tokens + /api/v1
 * Access in memory; refresh in sessionStorage (same-origin MVP).
 */
(function () {
  const API = "/api/v1";
  const REFRESH_KEY = "portal_pwa_refresh";
  const SEEN_KEY = "portal_pwa_seen_v1";
  let accessToken = null;
  let deferredInstall = null;
  let lastPayload = null;
  let lastI18n = null;

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getRefresh() {
    try {
      return sessionStorage.getItem(REFRESH_KEY);
    } catch (_) {
      return null;
    }
  }

  function setRefresh(token) {
    try {
      if (token) sessionStorage.setItem(REFRESH_KEY, token);
      else sessionStorage.removeItem(REFRESH_KEY);
    } catch (_) {}
  }

  function clearSession() {
    accessToken = null;
    setRefresh(null);
  }

  async function api(path, options) {
    const opts = options || {};
    const headers = Object.assign({ Accept: "application/json" }, opts.headers || {});
    if (opts.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    if (accessToken) headers.Authorization = "Bearer " + accessToken;

    let res = await fetch(API + path, {
      method: opts.method || "GET",
      headers,
      body: opts.body || undefined,
      credentials: "same-origin",
    });

    if (res.status === 401 && getRefresh() && path !== "/auth/refresh" && path !== "/auth/login") {
      const ok = await refreshTokens();
      if (ok) {
        headers.Authorization = "Bearer " + accessToken;
        res = await fetch(API + path, {
          method: opts.method || "GET",
          headers,
          body: opts.body || undefined,
          credentials: "same-origin",
        });
      }
    }
    return res;
  }

  async function refreshTokens() {
    const rt = getRefresh();
    if (!rt) return false;
    const res = await fetch(API + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: rt, client: "pwa" }),
      credentials: "same-origin",
    });
    if (!res.ok) {
      clearSession();
      return false;
    }
    const data = await res.json();
    accessToken = data.access_token;
    setRefresh(data.refresh_token);
    return true;
  }

  async function ensureAuthOrRedirect() {
    if (accessToken) return true;
    if (getRefresh()) {
      const ok = await refreshTokens();
      if (ok) return true;
    }
    window.location.replace("/m/login");
    return false;
  }

  function registerSW() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/m/sw.js", { scope: "/m/" }).catch(function () {});
  }

  function isIosSafari() {
    const ua = navigator.userAgent || "";
    const iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const safari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|Chrome|Android/.test(ua);
    return iOS && (safari || /Safari/.test(ua));
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches
      || window.navigator.standalone === true;
  }

  function bindInstall(btn) {
    const tip = qs("#pwa-install-tip");
    const tipClose = qs("#pwa-install-tip-close");
    function closeTip() {
      if (!tip) return;
      tip.hidden = true;
      if (btn) btn.focus();
    }
    if (tipClose && tip) {
      tipClose.addEventListener("click", closeTip);
    }

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredInstall = e;
      if (btn) btn.hidden = false;
    });

    if (btn) {
      // iOS: show A2HS tip (no beforeinstallprompt)
      if (isIosSafari() && !isStandalone()) {
        btn.hidden = false;
      }
      btn.addEventListener("click", async function () {
        if (deferredInstall) {
          deferredInstall.prompt();
          try { await deferredInstall.userChoice; } catch (_) {}
          deferredInstall = null;
          btn.hidden = true;
          return;
        }
        if (tip) {
          tip.hidden = false;
          if (tipClose) tipClose.focus();
        }
      });
    }
  }

  function i18nStr(key, fallback) {
    const el = qs("#pwa-i18n");
    if (!el || !el.dataset) return fallback;
    const val = el.dataset[key];
    return val || fallback;
  }

  function bindOffline() {
    const banner = qs("#pwa-offline");
    function sync() {
      if (!banner) return;
      banner.hidden = navigator.onLine;
    }
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    sync();
  }

  async function initLogin() {
    registerSW();
    if (getRefresh()) {
      const ok = await refreshTokens();
      if (ok) {
        window.location.replace("/m/");
        return;
      }
    }
    const form = qs("#pwa-login-form");
    const err = qs("#pwa-login-error");
    const btn = qs("#pwa-login-btn");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (err) {
        err.hidden = true;
        err.textContent = "";
      }
      if (btn) btn.disabled = true;
      try {
        const username = qs("#username").value.trim();
        const password = qs("#password").value;
        const res = await fetch(API + "/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ username: username, password: password, client: "pwa" }),
          credentials: "same-origin",
        });
        const data = await res.json().catch(function () {
          return {};
        });
        if (!res.ok) {
          if (err) {
            err.textContent = data.detail || "Usuário ou senha inválidos.";
            err.hidden = false;
          }
          return;
        }
        accessToken = data.access_token;
        setRefresh(data.refresh_token);
        window.location.replace("/m/");
      } catch (_) {
        if (err) {
          err.textContent = "Falha de rede. Tente novamente.";
          err.hidden = false;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }

  function statusLabel(status, i18n) {
    if (status === "available") return { text: i18n.msgAvailable, cls: "ok" };
    if (status === "not_yet_available") return { text: i18n.msgSoon, cls: "warn" };
    return { text: i18n.msgExpired, cls: "bad" };
  }

  function loadSeen() {
    try {
      return JSON.parse(localStorage.getItem(SEEN_KEY) || "{}") || {};
    } catch (_) {
      return {};
    }
  }

  function saveSeen(map) {
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify(map));
    } catch (_) {}
  }

  function fingerprint(item) {
    return String(item.acesso_id) + ":" + String(item.status) + ":" + String(item.documento_count || 0);
  }

  /** Novos acessos, downloads liberados ou documentos atualizados desde a última leitura. */
  function collectNotices(items, i18n) {
    const list = items || [];
    const seen = loadSeen();
    let initialized = false;
    try {
      initialized = localStorage.getItem(SEEN_KEY + "_init") === "1";
    } catch (_) {}

    // Primeira visita: registra baseline sem spam de notificações antigas
    if (!initialized) {
      markAllSeen(list);
      try {
        localStorage.setItem(SEEN_KEY + "_init", "1");
      } catch (_) {}
      return [];
    }

    const notices = [];
    list.forEach(function (item) {
      if (item.status === "expired") return;
      const id = String(item.acesso_id);
      const prev = seen[id];
      const title = (item.evento && item.evento.titulo) || ("#" + id);
      const docs = item.documento_count || (item.documentos || []).length || 0;
      const fp = fingerprint(item);

      if (!prev) {
        notices.push({
          acesso_id: item.acesso_id,
          kind: item.status === "available" ? "released" : "new",
          title: title,
          detail:
            (item.status === "available" ? i18n.msgNoticeReleased : i18n.msgNoticeNew) +
            " · " +
            docs +
            " " +
            i18n.msgNoticeDocs,
        });
        return;
      }
      if (prev.status !== "available" && item.status === "available") {
        notices.push({
          acesso_id: item.acesso_id,
          kind: "released",
          title: title,
          detail: i18n.msgNoticeReleased + " · " + docs + " " + i18n.msgNoticeDocs,
        });
        return;
      }
      if (prev.fp !== fp && item.status !== "expired") {
        notices.push({
          acesso_id: item.acesso_id,
          kind: "new",
          title: title,
          detail: i18n.msgNoticeNew + " · " + docs + " " + i18n.msgNoticeDocs,
        });
      }
    });
    return notices;
  }

  function markAllSeen(items) {
    const seen = loadSeen();
    (items || []).forEach(function (item) {
      seen[String(item.acesso_id)] = {
        status: item.status,
        fp: fingerprint(item),
        at: Date.now(),
      };
    });
    saveSeen(seen);
  }

  function isUnseen(item) {
    const seen = loadSeen();
    const prev = seen[String(item.acesso_id)];
    if (!prev) return item.status !== "expired";
    if (prev.status !== "available" && item.status === "available") return true;
    return prev.fp !== fingerprint(item) && item.status !== "expired";
  }

  function renderNotices(items, i18n) {
    const box = qs("#pwa-notices");
    const list = qs("#pwa-notices-list");
    if (!box || !list) return;
    const notices = collectNotices(items, i18n);
    list.innerHTML = "";
    if (!notices.length) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    notices.forEach(function (n) {
      const li = document.createElement("li");
      li.className = "pwa-notice pwa-notice-" + n.kind;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pwa-notice-btn";
      btn.innerHTML =
        "<strong>" +
        escapeHtml(n.title) +
        "</strong><span>" +
        escapeHtml(n.detail) +
        "</span>";
      btn.addEventListener("click", function () {
        const card = qs('#pwa-item-' + n.acesso_id);
        if (card) {
          card.scrollIntoView({ behavior: "smooth", block: "center" });
          card.classList.add("pwa-item-flash");
          setTimeout(function () {
            card.classList.remove("pwa-item-flash");
          }, 1200);
        }
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderList(payload, i18n) {
    const list = qs("#pwa-list");
    const status = qs("#pwa-status");
    if (!list) return;
    list.innerHTML = "";
    const items = (payload && payload.items) || [];
    renderNotices(items, i18n);
    if (!items.length) {
      if (status) {
        status.innerHTML =
          "<div class=\"pwa-empty\">" +
          "<p><strong>" +
          escapeHtml(i18n.msgEmpty) +
          "</strong></p>" +
          "<p class=\"pwa-empty-help\">" +
          escapeHtml(i18n.msgEmptyHelp) +
          "</p></div>";
      }
      return;
    }
    if (status) status.textContent = "";
    items.forEach(function (item) {
      const st = statusLabel(item.status, i18n);
      const ev = item.evento || {};
      const card = document.createElement("article");
      card.className = "pwa-item" + (isUnseen(item) ? " pwa-item-new" : "");
      card.id = "pwa-item-" + item.acesso_id;
      if (isUnseen(item)) {
        const tag = document.createElement("span");
        tag.className = "pwa-new-tag";
        tag.textContent = item.status === "available" ? i18n.msgNoticeReleased : i18n.msgNoticeNew;
        card.appendChild(tag);
      }
      const title = document.createElement("h2");
      title.textContent = ev.titulo || ("Evento #" + (ev.id || item.acesso_id));
      card.appendChild(title);
      const meta = document.createElement("span");
      meta.className = "pwa-meta";
      const bits = [];
      if (ev.data_inicio) bits.push(String(ev.data_inicio).slice(0, 16).replace("T", " "));
      if (ev.local) bits.push(ev.local);
      meta.textContent = bits.join(" · ");
      card.appendChild(meta);
      const badge = document.createElement("span");
      badge.className = "pwa-badge " + st.cls;
      badge.textContent = st.text;
      card.appendChild(badge);
      const docs = document.createElement("div");
      docs.className = "pwa-docs";
      (item.documentos || []).forEach(function (doc) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pwa-doc-btn";
        const title = doc.title || doc.instrumento_nome || doc.label || "Partitura";
        const canOpen = item.status === "available" && (doc.view_ticket_path || doc.download_path);
        b.textContent = canOpen ? ((i18n.msgOpen || "Abrir partitura") + " — " + title) : title;
        b.disabled = !canOpen;
        if (canOpen) {
          b.addEventListener("click", function () {
            openPdf(doc, title);
          });
        }
        docs.appendChild(b);
      });
      if (!(item.documentos || []).length) {
        const empty = document.createElement("p");
        empty.className = "pwa-meta";
        empty.textContent = i18n.msgLoadError || "Sem documentos";
        docs.appendChild(empty);
      }
      card.appendChild(docs);
      list.appendChild(card);
    });
  }

  function setPdfViewerUrl(frame, url) {
    if (!frame) return;
    if (frame._blobUrl && frame._blobUrl !== url) {
      try { URL.revokeObjectURL(frame._blobUrl); } catch (_) {}
      frame._blobUrl = null;
    }
    frame.setAttribute("type", "application/pdf");
    if ("data" in frame) {
      frame.data = url || "";
      frame.setAttribute("data", url || "");
    }
    frame.src = url || "about:blank";
  }

  let pdfReturnFocus = null;

  function closePdfSheet() {
    const sheet = qs("#pwa-pdf-sheet");
    const frame = qs("#pwa-pdf-frame");
    if (frame) {
      if (frame._blobUrl) {
        try { URL.revokeObjectURL(frame._blobUrl); } catch (_) {}
        frame._blobUrl = null;
      }
      setPdfViewerUrl(frame, "");
    }
    if (sheet) sheet.hidden = true;
    if (pdfReturnFocus && typeof pdfReturnFocus.focus === "function") {
      try { pdfReturnFocus.focus(); } catch (_) {}
    }
    pdfReturnFocus = null;
  }

  async function openPdf(doc, title) {
    const sheet = qs("#pwa-pdf-sheet");
    const frame = qs("#pwa-pdf-frame");
    const titleEl = qs("#pwa-pdf-title");
    const hint = qs("#pwa-pdf-hint");
    const closeBtn = qs("#pwa-pdf-close");
    if (!sheet || !frame) return;
    pdfReturnFocus = document.activeElement;
    if (titleEl) titleEl.textContent = title || "Partitura";
    if (hint) hint.textContent = i18nStr("pdfLoading", "Carregando partitura…");
    sheet.hidden = false;
    if (closeBtn) closeBtn.focus();
    setPdfViewerUrl(frame, "");

    try {
      let viewUrl = null;

      if (doc.view_ticket_path) {
        const ticketPath = doc.view_ticket_path.startsWith("/api/v1")
          ? doc.view_ticket_path.slice("/api/v1".length)
          : doc.view_ticket_path;
        const tres = await api(ticketPath, { method: "POST", body: "{}" });
        if (!tres.ok) throw new Error("ticket");
        const tdata = await tres.json();
        viewUrl = tdata.view_url;
        if (titleEl && tdata.title) titleEl.textContent = tdata.title;
      }

      if (!viewUrl && doc.download_path) {
        const res = await fetch(doc.download_path, {
          headers: { Authorization: "Bearer " + accessToken, Accept: "application/pdf" },
          credentials: "same-origin",
        });
        if (!res.ok) throw new Error("pdf");
        const buf = await res.arrayBuffer();
        const blob = new Blob([buf], { type: "application/pdf" });
        viewUrl = URL.createObjectURL(blob);
        frame._blobUrl = viewUrl;
      }

      if (!viewUrl) throw new Error("no-url");

      // Smartphone / tablet touch (incl. iPad): navegação full-page → viewer nativo
      const isTouch = ("ontouchstart" in window) || (navigator.maxTouchPoints > 0);
      if (isTouch && viewUrl.indexOf("/m/pdf/") === 0) {
        window.location.assign(viewUrl);
        return;
      }

      setPdfViewerUrl(frame, viewUrl);
      if (hint) {
        const tpl = i18nStr(
          "pdfFallback",
          'Se a partitura não aparecer, <a class="pwa-pdf-openlink" href="{url}" target="_blank" rel="noopener">toque aqui para abrir</a>.'
        );
        hint.innerHTML = tpl.replace(/\{url\}/g, viewUrl);
      }
    } catch (err) {
      closePdfSheet();
      const offline = typeof navigator !== "undefined" && navigator.onLine === false;
      const msg = offline
        ? i18nStr("offline", "Sem conexão. Verifique a internet e tente de novo.")
        : i18nOpenError();
      alert(msg);
    }
  }

  function i18nOpenError() {
    return i18nStr("loadError", "Não foi possível abrir o PDF.");
  }

  async function initApp(i18n) {
    registerSW();
    bindInstall(qs("#pwa-install"));
    bindOffline();
    const ok = await ensureAuthOrRedirect();
    if (!ok) return;

    const logout = qs("#pwa-logout");
    if (logout) {
      logout.addEventListener("click", async function () {
        const rt = getRefresh();
        try {
          if (rt) {
            await fetch(API + "/auth/logout", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: rt }),
            });
          }
        } catch (_) {}
        clearSession();
        window.location.replace("/m/login");
      });
    }

    const closePdf = qs("#pwa-pdf-close");
    if (closePdf) {
      closePdf.addEventListener("click", closePdfSheet);
    }

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      const tip = qs("#pwa-install-tip");
      if (tip && !tip.hidden) {
        tip.hidden = true;
        const installBtn = qs("#pwa-install");
        if (installBtn) installBtn.focus();
        return;
      }
      const sheet = qs("#pwa-pdf-sheet");
      if (sheet && !sheet.hidden) closePdfSheet();
    });

    const clearBtn = qs("#pwa-notices-clear");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (lastPayload) markAllSeen(lastPayload.items || []);
        renderList(lastPayload || { items: [] }, lastI18n || i18n);
      });
    }

    const meRes = await api("/auth/me");
    if (meRes.ok) {
      const me = await meRes.json();
      const userEl = qs("#pwa-user");
      if (userEl) {
        const name = (me.musician && me.musician.full_name) || me.username;
        userEl.textContent = name || "";
      }
    }

    const status = qs("#pwa-status");
    const listRes = await api("/me/partituras");
    if (listRes.status === 403) {
      if (status) status.textContent = i18n.msgNoLink;
      return;
    }
    if (!listRes.ok) {
      if (status) status.textContent = i18n.msgLoadError;
      return;
    }
    const payload = await listRes.json();
    lastPayload = payload;
    lastI18n = i18n;
    renderList(payload, i18n);
  }

  window.PortalPwa = { initLogin: initLogin, initApp: initApp };
})();
