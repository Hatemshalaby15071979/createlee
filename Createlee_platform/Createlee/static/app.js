/* Createlee / Engeznee — plain vanilla JS, no build step, no dependencies. */
(function () {
  "use strict";
  var SID = null;
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var fmtBytes = function (n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
    return (n / 1048576).toFixed(2) + " MB";
  };
  var toast = function (msg) {
    var t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(t._timer); t._timer = setTimeout(function () { t.hidden = true; }, 4200);
  };
  var api = function (url, opts) {
    return fetch(url, opts || {}).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "HTTP " + r.status }; });
    });
  };
  var post = function (url, body) {
    return api(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}) });
  };

  /* ---------------- rendering ---------------- */
  function renderChat(history) {
    var log = $("chatLog");
    log.innerHTML = (history || []).map(function (m) {
      var trace = (m.trace || []).map(function (t) {
        var mark = t.ok === false ? "✗" : "✓";
        return '<div class="trace">🔧 ' + esc(t.tool || "tool") + " " + mark +
          (t.summary ? " — " + esc(String(t.summary).slice(0, 220)) : "") + "</div>";
      }).join("");
      var badge = m.source === "fallback"
        ? '<span class="srcbadge offline">offline</span>' : "";
      return '<div class="bubble ' + (m.role === "user" ? "user" : "engeznee") + '">' +
        '<span class="who">' + (m.role === "user" ? "You" : "Engeznee") + badge + '</span>' +
        esc(m.text) + trace + "</div>";
    }).join("") || '<div class="empty">Say <b>help</b> to see what Engeznee can do, or <b>generate all</b> to stage documents.</div>';
    log.scrollTop = log.scrollHeight;
  }

  function renderUploads(uploads) {
    var el = $("uploadList");
    if (!uploads || !uploads.length) { el.innerHTML = '<div class="empty">No files uploaded.</div>'; return; }
    el.innerHTML = uploads.map(function (u) {
      var fmts = Object.keys(u.formats || {}).slice(0, 5).map(function (k) {
        return k + "=" + u.formats[k];
      }).join(", ");
      return '<div class="upitem"><b>' + esc(u.filename) + '</b>' +
        (u.is_sample ? '<span class="tag sample">bundled sample</span>' : '<span class="tag">uploaded</span>') +
        '<div class="meta">' + esc(u.kind || "?") + ' · ' + u.rows + ' rows · ' +
        (u.columns || []).length + ' cols · ' + fmtBytes(u.size_bytes) +
        (u.error ? ' · <span style="color:#b3352c">' + esc(u.error) + '</span>' : "") +
        (fmts ? '<br>' + esc(fmts) : "") + "</div></div>";
    }).join("");
  }

  function renderStaged(staged) {
    var panel = $("reviewPanel"), list = $("stagedList");
    if (!staged || !staged.length) {
      panel.hidden = true; list.innerHTML = "";
      $("reviewedChk").checked = false; $("approveBtn").disabled = true;
      return;
    }
    panel.hidden = false;
    list.innerHTML = staged.map(function (s) {
      return '<div class="stage">' +
        '<input type="checkbox" class="stagechk" value="' + s.index + '" checked>' +
        '<div class="info"><div class="t">' + esc(s.title) +
        ' <span class="tag">' + esc(s.domain) + '</span></div>' +
        '<div class="m">' + esc(s.document_id) + ' · ' + esc(s.generated_at_iso8601) +
        ' · ' + esc(s.formats.join(", ")) + ' · ' + esc(s.review_status) + '</div></div>' +
        '<button class="ghost" data-preview="' + s.index + '">Preview</button></div>';
    }).join("");
    list.querySelectorAll("[data-preview]").forEach(function (b) {
      b.addEventListener("click", function () { openPreview(b.getAttribute("data-preview")); });
    });
  }

  function renderFiles(files) {
    var el = $("filesList");
    if (!files || !files.length) { el.innerHTML = '<div class="empty">No approved files yet.</div>'; return; }
    el.innerHTML = files.map(function (f) {
      return '<div class="fileitem"><a href="' + esc(f.url) + '" download>' + esc(f.filename) + '</a>' +
        '<div class="fm">' + esc((f.format || "").toUpperCase()) + ' · ' + fmtBytes(f.size_bytes) +
        (f.approved_at_iso8601 ? ' · approved ' + esc(f.approved_at_iso8601) : "") + '</div></div>';
    }).join("");
  }

  function renderState(st) {
    if (!st) return;
    SID = st.sid;
    try { localStorage.setItem("createlee_sid", SID); } catch (e) {}
    renderChat(st.history);
    renderUploads(st.uploads);
    renderStaged(st.staged);
    renderFiles(st.outputs);
    if (st.email_prefill) {
      if (!$("emailTo").value && st.email_prefill.to) $("emailTo").value = st.email_prefill.to;
      if (!$("emailSubject").value && st.email_prefill.subject) $("emailSubject").value = st.email_prefill.subject;
    }
  }

  function applyStatus(status) {
    $("badgeTime").textContent = "UTC " + status.server_time_iso8601;
    var oo = status.ollama.ollama;
    $("badgeLlm").textContent = "LLM: " + status.ollama.active +
      (oo && oo.available && oo.selected ? " · " + oo.selected : "");
    $("badgeMail").textContent = "Email: " + status.email.mode;
    var o = status.ollama.ollama, e = status.email;
    $("statusBox").textContent = [
      "Createlee " + status.version + " / Engeznee",
      "Server time : " + status.server_time_iso8601,
      "",
      "Ollama local : " + (o.available ? "AVAILABLE" : "not reachable here"),
      "  host       : " + (o.host || "-"),
      o.available ? "  models     : " + (o.models || []).join(", ") : "  auto-detected when you run locally",
      "Cloud model  : " + (status.ollama.cloud.available ? "configured" : "not configured"),
      "Active LLM   : " + status.ollama.active,
      "",
      "Email        : " + e.mode,
      "  from       : " + e.from,
      "  smtp       : " + e.host + ":" + e.port,
      "  no creds   -> .eml draft, never a silent send",
      "",
      "Web enrich   : " + (status.web_enabled ? "enabled" : "disabled"),
      "Formats      : " + status.formats.join(", "),
      "Max upload   : " + status.max_upload_mb + " MB",
      "Time standard: ISO-8601 / UTC"
    ].join("\n");
  }

  /* ---------------- actions ---------------- */
  function send(msg) {
    msg = (msg == null ? $("msgInput").value : msg).trim();
    if (!msg) return;
    $("msgInput").value = "";
    $("sendBtn").disabled = true;
    $("msgInput").disabled = true;
    var cs = $("chatStatus");
    var started = Date.now();
    cs.hidden = false;
    cs.textContent = "Engeznee is thinking…";
    var tick = setInterval(function () {
      cs.textContent = "Engeznee is thinking… " + Math.round((Date.now() - started) / 1000) + "s";
    }, 1000);
    post("/api/chat", { sid: SID, message: msg }).then(function (d) {
      if (d.ok) renderState(d.state);
      else toast(d.error || "Request failed");
    }).catch(function (e) { toast("Network error: " + e); })
      .finally(function () {
        clearInterval(tick);
        cs.hidden = true;
        $("sendBtn").disabled = false;
        $("msgInput").disabled = false;
        $("msgInput").focus();
      });
  }

  function openPreview(index) {
    api("/api/preview/" + encodeURIComponent(SID) + "/" + index).then(function (d) {
      if (!d.ok) { toast(d.error || "Preview unavailable"); return; }
      showModalText(d.title + " — preview (staged, not yet saved)", d.text);
    });
  }

  function refreshFiles() {
    api("/api/files").then(function (d) { if (d.ok) renderFiles(d.files); });
  }

  /* ---------------- system library browser ---------------- */
  function showModalText(title, text) {
    $("modalTitle").textContent = title;
    $("modalText").textContent = text == null ? "" : text;
    $("modalText").hidden = false;
    $("modalTable").innerHTML = "";
    $("modalTable").hidden = true;
    $("modal").hidden = false;
  }

  function showModalTable(title, html) {
    $("modalTitle").textContent = title;
    $("modalTable").innerHTML = html;
    $("modalTable").hidden = false;
    $("modalText").textContent = "";
    $("modalText").hidden = true;
    $("modal").hidden = false;
  }

  function renderLibrarySummary(status) {
    var el = $("librarySummary");
    if (!status || !status.built) {
      el.innerHTML = '<div class="empty">' +
        (status && status.message ? esc(status.message) : "System library not built yet.") + "</div>";
      return;
    }
    var rc = status.row_counts || {}, rec = status.reconciliation || {};
    el.innerHTML = '<div class="libfacts">' +
      '<span class="fact"><b>as-of</b> ' + esc(status.as_of) + '</span>' +
      '<span class="fact"><b>files</b> ' + esc(status.file_count) + '</span>' +
      '<span class="fact"><b>corpus</b> ' + esc(rc.corpus) + ' procedures</span>' +
      '<span class="fact"><b>labels</b> ' + esc(rc.labels) + ' tickets</span>' +
      '<span class="fact"><b>reconciled</b> ' + esc(rec.fully_reconciled) + "/" + esc(rec.keys_total) + '</span>' +
      '<span class="fact"><b>rows deleted</b> ' + esc(rec.rows_deleted) + '</span>' +
      '<span class="fact"><b>findings</b> ' + esc((status.findings || []).length) + '</span>' +
      '<span class="fact"><b>web refs</b> ' + esc(status.web_reference_count) + '</span>' +
      "</div>";
  }

  function renderLibraryTree(groups) {
    var el = $("libraryTree");
    if (!groups || !groups.length) {
      el.innerHTML = '<div class="empty">No library files. Click "Build / refresh library".</div>';
      return;
    }
    el.innerHTML = groups.map(function (g) {
      var items = g.files.map(function (f) {
        var meta = (f.format === "csv" ? esc(f.rows) + " rows · " + esc(f.columns) + " cols · " : "") +
          fmtBytes(f.size_bytes);
        return '<div class="libfile" data-path="' + esc(f.path) + '">' +
          '<span class="lficon">' + esc(String(f.format || "?").toUpperCase()) + '</span>' +
          '<span class="lfname">' + esc(f.name) + '</span>' +
          '<span class="lfmeta">' + meta + '</span></div>';
      }).join("");
      return '<div class="libgroup"><div class="libgrouphead">' + esc(g.label) + '</div>' + items + "</div>";
    }).join("");
    el.querySelectorAll(".libfile").forEach(function (b) {
      b.addEventListener("click", function () { openLibraryFile(b.getAttribute("data-path")); });
    });
  }

  function loadLibrary() {
    api("/api/library/status").then(function (d) { if (d.ok) renderLibrarySummary(d); });
    api("/api/library/files").then(function (d) { if (d.ok) renderLibraryTree(d.groups); });
  }

  function buildLibrary() {
    $("buildLibraryBtn").disabled = true;
    post("/api/library", { sid: SID }).then(function (d) {
      if (d.ok) { toast("System library built."); loadLibrary(); }
      else toast(d.error || "Library build failed");
    }).catch(function (e) { toast("Network error: " + e); })
      .finally(function () { $("buildLibraryBtn").disabled = false; });
  }

  function openLibraryFile(path) {
    api("/api/library/file/" + encodeURIComponent(path)).then(function (d) {
      if (!d.ok) { toast(d.error || "File unavailable"); return; }
      if (d.binary) {
        showModalText(d.name + " (binary file)",
          "This is a binary " + String(d.format).toUpperCase() + " file.\n\n" +
          "Open it in a viewer — download:\n" + d.download_url);
        return;
      }
      if (d.format === "csv") {
        var cols = d.header || [], rows = d.rows || [];
        var html = '<table class="libtable"><thead><tr>' +
          cols.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") +
          "</tr></thead><tbody>" +
          rows.map(function (r) {
            return "<tr>" + cols.map(function (c, i) {
              return "<td>" + esc(r[i] == null ? "" : r[i]) + "</td>";
            }).join("") + "</tr>";
          }).join("") + "</tbody></table>";
        var note = d.truncated ? '<div class="hint">Showing first 1000 of ' + d.row_count + " rows.</div>" : "";
        showModalTable(d.name + " — " + d.row_count + " row(s)", note + html);
      } else {
        showModalText(d.name, d.text || "(empty)");
      }
    });
  }

  function approve() {
    var selected = Array.from(document.querySelectorAll(".stagechk:checked"))
      .map(function (c) { return parseInt(c.value, 10); });
    if (!$("reviewedChk").checked) { toast("Tick the review checkbox first."); return; }
    if (!selected.length) { toast("Select at least one document."); return; }
    var action = $("actionSel").value;
    if (action !== "save" && !$("emailTo").value.trim()) {
      toast("Enter a recipient address, or choose 'Save'."); return;
    }
    $("approveBtn").disabled = true;
    post("/api/approve", {
      sid: SID, approved: true, selected: selected, action: action,
      email_to: $("emailTo").value.trim(),
      email_subject: $("emailSubject").value.trim(),
      email_body: $("emailBody").value.trim()
    }).then(function (d) {
      if (d.ok) {
        renderState(d.state);
        toast("Approved. " + (d.created || []).length + " file(s) created." +
              (d.email ? " Email: " + d.email.mode : ""));
        refreshFiles();
      } else { toast(d.error || "Approval failed"); }
    }).catch(function (e) { toast("Network error: " + e); })
      .finally(function () { $("approveBtn").disabled = false; });
  }

  function uploadFiles() {
    var files = $("fileInput").files;
    if (!files || !files.length) { toast("Choose one or more files first."); return; }
    var fd = new FormData(); fd.append("sid", SID || "");
    for (var i = 0; i < files.length; i++) fd.append("files", files[i]);
    $("uploadBtn").disabled = true;
    fetch("/api/upload", { method: "POST", body: fd }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) { renderState(d.state); $("fileInput").value = ""; toast("Uploaded and analysed."); }
        else toast(d.error || "Upload failed");
      }).catch(function (e) { toast("Upload error: " + e); })
      .finally(function () { $("uploadBtn").disabled = false; });
  }

  /* ---------------- settings + local model ---------------- */
  function renderSettings(d) {
    var models = d.models || [];
    var selModel = d.selected || (d.settings && d.settings.model) || "";
    $("modelSel").innerHTML = '<option value="">(auto)</option>' + models.map(function (m) {
      return '<option value="' + esc(m) + '"' + (m === selModel ? " selected" : "") + ">" +
        esc(m) + "</option>";
    }).join("");
    if (d.settings) {
      $("tempInput").value = d.settings.temperature;
      $("stepsInput").value = d.settings.max_steps;
      $("autostartChk").checked = !!d.settings.autostart;
    }
    var o = d.ollama || {};
    var txt;
    if (o.available) {
      txt = "Ollama up · " + (o.models || []).length + " model(s) · using " + (o.selected || "auto");
    } else {
      txt = "Ollama offline" + (o.binary ? " — binary found, press Start Ollama"
                                         : " — binary not found on PATH");
      if (o.last_start && o.last_start.detail) txt += " · " + o.last_start.detail;
    }
    $("settingsStatus").textContent = txt;
  }

  function loadSettings() {
    api("/api/settings").then(function (d) { if (d.ok) renderSettings(d); });
  }

  function saveSettings() {
    post("/api/settings", {
      model: $("modelSel").value,
      autostart: $("autostartChk").checked,
      temperature: parseFloat($("tempInput").value || "0.3"),
      max_steps: parseInt($("stepsInput").value || "6", 10)
    }).then(function (d) {
      if (d.ok) { renderSettings(d); toast("Settings saved."); }
      else toast(d.error || "Save failed");
    }).catch(function (e) { toast("Network error: " + e); });
  }

  function startOllama() {
    $("startOllamaBtn").disabled = true;
    $("settingsStatus").textContent = "Starting Ollama…";
    post("/api/ollama/start", {}).then(function (d) {
      renderSettings(d);
      toast(d.ok ? "Ollama is up." : ("Ollama: " + (d.detail || "failed")));
    }).catch(function (e) { toast("Network error: " + e); })
      .finally(function () { $("startOllamaBtn").disabled = false; });
  }

  /* ---------------- hand-off packs ---------------- */
  function renderHandoff(d) {
    var projects = d.projects || [];
    var asOf = projects.length ? projects[0].as_of : "";
    $("handoffSummary").innerHTML =
      '<div class="librow"><b>' + esc(d.files_written) + "</b> files written · as-of <b>" +
      esc(asOf) + "</b></div>" +
      '<div class="librow small">Overview: <code>' + esc(d.overview || "") + "</code></div>";
    $("handoffTree").innerHTML = projects.map(function (m) {
      var gen = (m.files || []).filter(function (f) {
        return String(f.client_action || "").indexOf("replace") === 0;
      }).length;
      var items = (m.files || []).map(function (f) {
        var rows = (f.generated_rows != null) ? esc(f.generated_rows) + " rows · " : "";
        return '<div class="libfile"><span class="lficon">FILE</span>' +
          '<span class="lfname">' + esc(f.filename) + "</span>" +
          '<span class="lfmeta">' + rows + esc(f.client_action || "") + "</span></div>";
      }).join("");
      return '<div class="libgroup"><div class="libgrouphead">' + esc(m.project) +
        " — " + (m.files || []).length + " file(s) · " + gen + " client-fillable · " +
        ((m.cannot_generate || []).length) + " org-only</div>" + items + "</div>";
    }).join("") || '<div class="empty">Not built yet. Click "Build / refresh hand-off packs".</div>';
  }

  function buildHandoff() {
    $("buildHandoffBtn").disabled = true;
    post("/api/handoff", { sid: SID }).then(function (d) {
      if (d.ok) { toast("Hand-off packs built."); renderHandoff(d); }
      else toast(d.error || "Hand-off build failed");
    }).catch(function (e) { toast("Network error: " + e); })
      .finally(function () { $("buildHandoffBtn").disabled = false; });
  }

  /* ---------------- wiring ---------------- */
  function init() {
    var saved = null;
    try { saved = localStorage.getItem("createlee_sid"); } catch (e) {}
    post("/api/session", { sid: saved }).then(function (d) {
      if (d.ok) { renderState(d.state); $("statusBox").textContent = d.status; }
    });
    api("/api/status").then(function (d) { if (d.ok) applyStatus(d); });
    refreshFiles();
    loadLibrary();
    loadSettings();

    $("saveSettingsBtn").addEventListener("click", saveSettings);
    $("startOllamaBtn").addEventListener("click", startOllama);
    $("refreshModelsBtn").addEventListener("click", loadSettings);

    $("sendBtn").addEventListener("click", function () { send(); });
    $("msgInput").addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });
    $("uploadBtn").addEventListener("click", uploadFiles);
    $("dropClearBtn").addEventListener("click", function () { $("fileInput").value = ""; });
    $("refreshFilesBtn").addEventListener("click", refreshFiles);
    $("buildLibraryBtn").addEventListener("click", buildLibrary);
    $("refreshLibraryBtn").addEventListener("click", loadLibrary);
    $("buildHandoffBtn").addEventListener("click", buildHandoff);
    $("approveBtn").addEventListener("click", approve);
    $("modalClose").addEventListener("click", function () { $("modal").hidden = true; });
    $("modal").addEventListener("click", function (e) { if (e.target === $("modal")) $("modal").hidden = true; });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") $("modal").hidden = true; });

    $("chips").addEventListener("click", function (e) {
      if (e.target.dataset && e.target.dataset.cmd) send(e.target.dataset.cmd);
    });

    $("reviewedChk").addEventListener("change", function () {
      $("approveBtn").disabled = !$("reviewedChk").checked;
      $("approveHint").textContent = $("reviewedChk").checked
        ? "Ready. Choose an action, then press Approve & Execute."
        : "Tick the review checkbox to enable.";
    });
    $("actionSel").addEventListener("change", function () {
      var emailOn = $("actionSel").value !== "save";
      $("emailTo").disabled = !emailOn; $("emailSubject").disabled = !emailOn;
      $("emailBody").disabled = !emailOn;
    });
    $("actionSel").dispatchEvent(new Event("change"));

    $("loadSamplesBtn").addEventListener("click", function () {
      post("/api/load-samples", { sid: SID }).then(function (d) {
        if (d.ok) { renderState(d.state); toast("Sample pack loaded."); }
      });
    });
    $("clearUploadsBtn").addEventListener("click", function () {
      if (!confirm("Clear all uploads and staged drafts? Approved files in outputs/ are kept.")) return;
      post("/api/clear-uploads", { sid: SID }).then(function (d) {
        if (d.ok) { renderState(d.state); toast("Uploads cleared."); }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
