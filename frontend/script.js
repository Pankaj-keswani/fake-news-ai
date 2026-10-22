/* Fake News Detector — frontend */
(() => {
  "use strict";

  // Same server in production; when index.html is opened straight from disk, talk to the local backend.
  const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:5000" : "";
  const MAX_LEN = 5000;
  const HISTORY_KEY = "fnd_history_v1";
  const HISTORY_MAX = 20;
  const SOURCES_SHOWN = 5;

  const $ = (id) => document.getElementById(id);
  const el = {
    form: $("checkForm"), input: $("newsInput"), analyze: $("analyzeBtn"), clear: $("clearBtn"),
    paste: $("pasteBtn"), voice: $("voiceBtn"), voiceLabel: $("voiceLabel"), count: $("charCount"),
    linkHint: $("linkHint"), status: $("status"), progress: $("progress"),
    result: $("result"), stamp: $("stamp"), stampText: $("stampText"), verdictText: $("verdictText"),
    meter: $("meterFill"), score: $("scoreText"), conf: $("confText"), tags: $("tags"),
    summary: $("resultSummary"), reason: $("reasonText"),
    claimsBlock: $("claimsBlock"), claims: $("claimsList"),
    flagsBlock: $("flagsBlock"), flags: $("flagsList"),
    adviceBlock: $("adviceBlock"), advice: $("adviceText"),
    sourcesBlock: $("sourcesBlock"), sources: $("sourcesList"), moreSources: $("moreSourcesBtn"),
    wa: $("waBtn"), copy: $("copyBtn"), share: $("shareBtn"),
    feedbackLabel: $("feedbackLabel"),
    errorBox: $("errorBox"), errorText: $("errorText"), retry: $("retryBtn"),
    history: $("historyList"), historyEmpty: $("historyEmpty"), clearHistory: $("clearHistoryBtn"),
    theme: $("themeBtn"),
  };

  const VERDICT = {
    "true":           { cls: "true",    label: "True",           stamp: "True" },
    "false":          { cls: "false",   label: "False",          stamp: "False" },
    "partially true": { cls: "partial", label: "Partly true",    stamp: "Misleading" },
    "unverifiable":   { cls: "unver",   label: "Unverifiable",   stamp: "Unverified" },
  };
  const SOURCE_TYPE = {
    factcheck: "Fact-check", official: "Official", wire: "News agency",
    major: "News outlet", reference: "Reference", other: "Other site",
  };
  const CATEGORY_LABEL = { Scam: "Possible scam" };

  let busy = false;
  let current = null;        // { text, result }
  let progressTimers = [];

  // ------------------------------------------------------------------ storage (never throws)
  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode / full */ }
    },
  };

  // ------------------------------------------------------------------ helpers
  const verdictInfo = (v) => VERDICT[String(v || "").toLowerCase()] || VERDICT.unverifiable;

  function node(tag, opts = {}, ...children) {
    const n = document.createElement(tag);
    if (opts.cls) n.className = opts.cls;
    if (opts.text != null) n.textContent = opts.text;
    if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) n.setAttribute(k, v);
    children.forEach((c) => c && n.appendChild(c));
    return n;
  }

  const setStatus = (text) => { el.status.textContent = text || ""; };

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function hasUrl(text) { return /https?:\/\/\S+/i.test(text); }

  // ------------------------------------------------------------------ input UX
  function updateCount() {
    const len = el.input.value.length;
    el.count.textContent = `${len} / ${MAX_LEN}`;
    el.count.classList.toggle("warn", len > MAX_LEN * 0.9);
    el.linkHint.hidden = !hasUrl(el.input.value);
  }
  el.input.addEventListener("input", updateCount);

  const isTouch = window.matchMedia("(pointer: coarse)").matches;
  el.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !isTouch && !e.isComposing) {
      e.preventDefault();
      analyze();
    }
  });

  el.form.addEventListener("submit", (e) => { e.preventDefault(); analyze(); });

  el.clear.addEventListener("click", () => {
    el.input.value = "";
    updateCount();
    hideResult();
    setStatus("");
    el.input.focus();
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      el.input.value = chip.dataset.example;
      updateCount();
      analyze();
    });
  });

  el.paste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (!text) { setStatus("Your clipboard is empty."); return; }
      el.input.value = text.slice(0, MAX_LEN);
      updateCount();
      setStatus("Pasted from clipboard.");
    } catch {
      el.input.focus();
      setStatus("Press Ctrl+V (or long-press → Paste) to paste your message.");
    }
  });

  el.retry.addEventListener("click", () => analyze());

  // ------------------------------------------------------------------ progress steps
  function startProgress() {
    el.progress.hidden = false;
    const steps = [...el.progress.querySelectorAll("li")];
    steps.forEach((s) => s.classList.remove("active", "done"));
    const go = (i) => {
      steps.forEach((s, j) => { s.classList.toggle("done", j < i); s.classList.toggle("active", j === i); });
    };
    go(0);
    progressTimers = [setTimeout(() => go(1), 900), setTimeout(() => go(2), 2600)];
  }
  function stopProgress() {
    progressTimers.forEach(clearTimeout);
    progressTimers = [];
    el.progress.hidden = true;
  }

  function setBusy(on) {
    busy = on;
    el.analyze.disabled = on;
    el.analyze.classList.toggle("is-busy", on);
    el.analyze.querySelector(".btn-label").textContent = on ? "Checking…" : "Check this message";
  }

  // ------------------------------------------------------------------ analyze
  async function analyze() {
    if (busy) return;
    const text = el.input.value.trim();
    if (!text) {
      setStatus("Paste or type a message first.");
      el.input.focus();
      return;
    }
    if (text.length > MAX_LEN) {
      setStatus(`That's too long — keep it under ${MAX_LEN} characters.`);
      return;
    }

    hideResult();
    setBusy(true);
    setStatus("");
    startProgress();

    let res, data;
    try {
      res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
    } catch {
      finish();
      showError("Couldn't reach the server. Check your internet connection and try again.");
      return;
    }

    try {
      data = await res.json();
    } catch {
      finish();
      showError(`The server sent an unexpected response (error ${res.status}). Try again in a moment.`);
      return;
    }
    finish();

    if (data && typeof data.error === "string") { showError(data.error); return; }
    if (!data || data.verdict === "Error" || data.error === true) {
      showError((data && data.reason) || "Something went wrong while checking. Try again.");
      return;
    }

    current = { text, result: data };
    renderResult(data, { animate: true });
    addHistory(text, data);
    setStatus(data.cached ? "Checked recently — showing the saved result." : "");
  }

  function finish() { stopProgress(); setBusy(false); }

  // ------------------------------------------------------------------ render result
  function hideResult() {
    el.result.hidden = true;
    el.errorBox.hidden = true;
  }

  function showError(message) {
    el.result.hidden = true;
    el.errorText.textContent = message;
    el.errorBox.hidden = false;
    el.errorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderResult(d, { animate = false } = {}) {
    el.errorBox.hidden = true;
    const info = verdictInfo(d.verdict);
    const score = Math.max(0, Math.min(100, Number(d.score) || 0));

    el.result.dataset.v = info.cls;
    el.stampText.textContent = info.stamp;
    el.verdictText.textContent = info.label;
    el.score.textContent = `Credibility ${score} / 100`;
    el.conf.textContent = `AI confidence: ${d.confidence || "medium"}`;
    el.meter.style.width = "0%";

    // tags
    el.tags.replaceChildren();
    if (d.category && d.category !== "Other") el.tags.appendChild(node("li", { text: CATEGORY_LABEL[d.category] || d.category }));
    const langName = { hindi: "हिन्दी", hinglish: "Hinglish", english: "English" }[d.language];
    if (langName) el.tags.appendChild(node("li", { text: langName }));
    if (d.input_type === "link" || d.input_type === "text+link") el.tags.appendChild(node("li", { text: "Read from link" }));
    if (d.checked_at) el.tags.appendChild(node("li", { text: `Checked ${formatDate(d.checked_at)}` }));

    el.summary.textContent = d.summary || info.label;
    el.reason.textContent = d.reason || "";

    // claims
    el.claims.replaceChildren();
    const claims = Array.isArray(d.claims) ? d.claims : [];
    claims.forEach((c) => {
      const ci = verdictInfo(c.verdict);
      el.claims.appendChild(node("li", {},
        node("span", { cls: `claim-v ${ci.cls}`, text: ci.label }),
        node("span", { text: c.claim }),
        c.note ? node("span", { cls: "claim-note", text: c.note }) : null));
    });
    el.claimsBlock.hidden = claims.length === 0;

    // warning signs = AI red flags + offline writing patterns
    el.flags.replaceChildren();
    (d.red_flags || []).forEach((f) => el.flags.appendChild(node("li", { text: f })));
    (d.signals || []).forEach((s) => el.flags.appendChild(node("li", { cls: "pattern" },
      document.createTextNode(s), node("span", { cls: "kind", text: "writing pattern" }))));
    el.flagsBlock.hidden = el.flags.children.length === 0;

    el.advice.textContent = d.advice || "";
    el.adviceBlock.hidden = !d.advice;

    // sources
    el.sources.replaceChildren();
    const sources = Array.isArray(d.sources) ? d.sources : [];
    sources.forEach((s, i) => {
      const url = String(s.url || "");
      const title = node(/^https?:\/\//i.test(url) ? "a" : "span", { text: s.title || url || "Untitled" });
      if (title.tagName === "A") { title.href = url; title.target = "_blank"; title.rel = "noopener noreferrer"; }
      const meta = node("span", { cls: "src-meta" },
        node("span", { text: `[${i + 1}]` }),
        node("span", { cls: `badge ${s.type}`, text: SOURCE_TYPE[s.type] || "Other site" }),
        s.source ? node("span", { text: s.source }) : null,
        s.date ? node("span", { text: formatDate(s.date) }) : null,
        s.cited ? node("span", { cls: "used", text: "used" }) : null);
      el.sources.appendChild(node("li", { cls: i >= SOURCES_SHOWN ? "extra" : "" }, title, meta));
    });
    el.sources.classList.remove("expanded");
    const extra = sources.length - SOURCES_SHOWN;
    el.moreSources.hidden = extra <= 0;
    el.moreSources.textContent = `Show ${extra} more source${extra === 1 ? "" : "s"}`;
    el.sourcesBlock.hidden = sources.length === 0;

    // share
    el.wa.href = "https://wa.me/?text=" + encodeURIComponent(shareText());
    el.share.hidden = !navigator.share;
    resetFeedback();

    el.result.hidden = false;
    requestAnimationFrame(() => { el.meter.style.width = `${score}%`; });
    if (animate) {
      el.stamp.classList.remove("landing");
      void el.stamp.offsetWidth; // restart animation
      el.stamp.classList.add("landing");
      el.result.focus({ preventScroll: true });
      el.result.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  el.moreSources.addEventListener("click", () => {
    el.sources.classList.add("expanded");
    el.moreSources.hidden = true;
  });

  // ------------------------------------------------------------------ share / copy
  function shareText() {
    if (!current) return "";
    const d = current.result;
    const info = verdictInfo(d.verdict);
    const pageUrl = location.protocol.startsWith("http") ? location.origin + location.pathname : "";
    const snippet = current.text.length > 160 ? current.text.slice(0, 160) + "…" : current.text;
    return [
      `Fact-check: ${info.label.toUpperCase()} (credibility ${d.score}/100)`,
      `“${snippet}”`,
      "",
      d.summary || d.reason || "",
      "",
      "Checked with an AI fact-checker — it can be wrong, so verify important news with trusted sources.",
      pageUrl,
    ].filter((line, i, arr) => !(line === "" && arr[i - 1] === "")).join("\n").trim();
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return; }
    const ta = node("textarea");
    ta.value = text;
    ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }

  el.copy.addEventListener("click", async () => {
    try { await copyText(shareText()); setStatus("Result copied."); } catch { setStatus("Couldn't copy. Select the text and copy it manually."); }
  });

  el.share.addEventListener("click", async () => {
    try { await navigator.share({ title: "Fact-check result", text: shareText() }); }
    catch (err) { if (!err || err.name !== "AbortError") setStatus("Couldn't open the share menu."); }
  });

  // ------------------------------------------------------------------ feedback
  function resetFeedback() {
    el.feedbackLabel.textContent = "Was this check helpful?";
    document.querySelectorAll(".fb-btn").forEach((b) => { b.disabled = false; b.setAttribute("aria-pressed", "false"); });
  }
  document.querySelectorAll(".fb-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!current) return;
      document.querySelectorAll(".fb-btn").forEach((b) => { b.disabled = true; b.setAttribute("aria-pressed", String(b === btn)); });
      el.feedbackLabel.textContent = "Thanks for the feedback.";
      try {
        await fetch(`${API_BASE}/api/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ helpful: btn.dataset.helpful === "true", verdict: current.result.verdict, text: current.text }),
        });
      } catch { /* feedback is best-effort */ }
    });
  });

  // ------------------------------------------------------------------ history
  let history = store.get(HISTORY_KEY, []);
  if (!Array.isArray(history)) history = [];

  function addHistory(text, result) {
    history = history.filter((h) => h.text !== text);
    history.unshift({ text, result, at: Date.now() });
    history = history.slice(0, HISTORY_MAX);
    store.set(HISTORY_KEY, history);
    renderHistory();
  }

  function renderHistory() {
    el.history.replaceChildren();
    history.forEach((item, idx) => {
      const info = verdictInfo(item.result && item.result.verdict);
      const open = node("button", { cls: "h-open", attrs: { type: "button" } },
        node("span", { cls: `h-v ${info.cls}`, text: info.label }),
        node("span", { cls: "h-text", text: item.text }),
        node("span", { cls: "h-date", text: formatDate(item.at) }));
      open.addEventListener("click", () => {
        el.input.value = item.text;
        updateCount();
        current = { text: item.text, result: item.result };
        renderResult(item.result, { animate: true });
        setStatus("Showing a saved check. Run it again for the latest news.");
      });
      const del = node("button", { cls: "h-del", text: "×", attrs: { type: "button", "aria-label": "Remove from history" } });
      del.addEventListener("click", () => {
        history.splice(idx, 1);
        store.set(HISTORY_KEY, history);
        renderHistory();
      });
      el.history.appendChild(node("li", {}, open, del));
    });
    el.historyEmpty.hidden = history.length > 0;
    el.clearHistory.hidden = history.length === 0;
  }

  el.clearHistory.addEventListener("click", () => {
    history = [];
    store.set(HISTORY_KEY, history);
    renderHistory();
  });

  // ------------------------------------------------------------------ voice input
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;
  let voiceLang = store.get("fnd_voice_lang", "en-IN");

  document.querySelectorAll(".seg-btn").forEach((b) => {
    b.setAttribute("aria-checked", String(b.dataset.lang === voiceLang));
    b.addEventListener("click", () => {
      voiceLang = b.dataset.lang;
      store.set("fnd_voice_lang", voiceLang);
      document.querySelectorAll(".seg-btn").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      if (recognition) recognition.lang = voiceLang;
    });
  });

  function setListening(on) {
    listening = on;
    el.voice.setAttribute("aria-pressed", String(on));
    el.voiceLabel.textContent = on ? "Stop" : "Speak";
  }

  if (!SpeechRecognition) {
    el.voice.disabled = true;
    el.voice.title = "Voice input works in Chrome and Edge";
  }

  el.voice.addEventListener("click", () => {
    if (!SpeechRecognition) { setStatus("Voice input works in Chrome and Edge."); return; }
    if (listening) { recognition.stop(); return; }

    recognition = new SpeechRecognition();
    recognition.lang = voiceLang;
    recognition.interimResults = true;
    recognition.continuous = true;
    const base = el.input.value.trim();

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      el.input.value = ((base ? base + " " : "") + transcript.trim()).slice(0, MAX_LEN);
      updateCount();
    };
    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") setStatus("Allow microphone access to use voice input.");
      else if (event.error === "no-speech") setStatus("Didn't hear anything. Try again.");
      else if (event.error !== "aborted") setStatus(`Voice input stopped (${event.error}).`);
    };
    recognition.onend = () => {
      setListening(false);
      if (el.status.textContent === "Listening…") setStatus("");
    };

    try {
      recognition.start();
      setListening(true);
      setStatus("Listening…");
    } catch {
      setStatus("Couldn't start voice input.");
    }
  });

  // ------------------------------------------------------------------ theme
  function applyThemeLabel() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    el.theme.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#0f1522" : "#2340c8");
  }
  el.theme.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("fnd_theme", next); } catch { /* ignore */ }
    applyThemeLabel();
  });

  // ------------------------------------------------------------------ init
  updateCount();
  renderHistory();
  applyThemeLabel();
})();
