/**
 * MetaPrompt UI — centered modal, focus management, pywebview bridge
 */

(function () {
  const $ = (id) => document.getElementById(id);

  const shell = $("app");
  const setup = $("setup");
  const main = $("main");
  const promptInput = $("prompt-input");
  const resultPanel = $("result-panel");
  const resultText = $("result-text");
  const errorText = $("error-text");
  const spinner = $("spinner");
  const copiedHint = $("copied-hint");
  const modeBadge = $("mode-badge");
  const copyBtn = $("copy-btn");
  const apiKeyInput = $("api-key-input");
  const saveKeyBtn = $("save-key-btn");
  const setupError = $("setup-error");

  let busy = false;
  let mode = "thorough";
  let focusTrapHandler = null;
  let lastFocusedBeforeSetup = null;

  const FOCUSABLE =
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  async function waitForBridge(timeoutMs = 5000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (api()) return api();
      await new Promise((r) => setTimeout(r, 50));
    }
    return null;
  }

  function getActiveDialog() {
    if (!setup.classList.contains("hidden")) return setup;
    if (!main.classList.contains("hidden")) return main;
    return null;
  }

  function enableFocusTrap(container) {
    disableFocusTrap();
    if (!container) return;

    focusTrapHandler = (e) => {
      if (e.key !== "Tab" || !container.contains(document.activeElement)) return;

      const nodes = Array.from(container.querySelectorAll(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (!nodes.length) return;

      const first = nodes[0];
      const last = nodes[nodes.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", focusTrapHandler);
  }

  function disableFocusTrap() {
    if (focusTrapHandler) {
      document.removeEventListener("keydown", focusTrapHandler);
      focusTrapHandler = null;
    }
  }

  function autosizeInput() {
    promptInput.style.height = "auto";
    const next = Math.min(Math.max(promptInput.scrollHeight, 28), 160);
    promptInput.style.height = next + "px";
  }

  function setBusy(on) {
    busy = on;
    promptInput.disabled = on;
    spinner.classList.toggle("hidden", !on);
    modeBadge.disabled = on;
  }

  function setExpanded(expanded) {
    main.classList.toggle("is-expanded", expanded);
    shell.dataset.state = expanded ? "expanded" : "main";
  }

  function showError(msg) {
    errorText.textContent = msg || "Something went wrong.";
    errorText.classList.remove("hidden");
    resultText.value = "";
    resultPanel.classList.remove("hidden");
    setExpanded(true);
    copiedHint.classList.remove("show");
  }

  function showResult(text, copied) {
    errorText.classList.add("hidden");
    resultText.value = text || "";
    resultPanel.classList.remove("hidden");
    setExpanded(true);
    if (copied) {
      copiedHint.classList.add("show");
      setTimeout(() => copiedHint.classList.remove("show"), 2200);
    }
  }

  function collapse() {
    resultPanel.classList.add("hidden");
    errorText.classList.add("hidden");
    resultText.value = "";
    copiedHint.classList.remove("show");
    setExpanded(false);
  }

  function reset() {
    setBusy(false);
    promptInput.value = "";
    autosizeInput();
    collapse();
  }

  function updateModeBadge() {
    modeBadge.textContent = mode;
    modeBadge.classList.toggle("fast", mode === "fast");
    modeBadge.setAttribute(
      "aria-label",
      `Optimization mode: ${mode}. Click to switch to ${mode === "fast" ? "thorough" : "fast"}.`
    );
  }

  function applySettings(settings) {
    mode = (settings && settings.mode) || "thorough";
    updateModeBadge();
  }

  function showSetup(visible) {
    setup.classList.toggle("hidden", !visible);
    main.classList.toggle("hidden", visible);
    shell.dataset.state = visible ? "setup" : "main";

    if (visible) {
      const bridge = api();
      if (bridge && bridge.ensure_setup_size) {
        bridge.ensure_setup_size();
      }
      lastFocusedBeforeSetup = document.activeElement;
      enableFocusTrap(setup);
      setTimeout(() => apiKeyInput.focus(), 40);
    } else {
      disableFocusTrap();
      enableFocusTrap(main);
      promptInput.focus();
    }
  }

  async function onShown() {
    const bridge = await waitForBridge();
    if (bridge && bridge.get_settings) {
      try {
        const settings = await bridge.get_settings();
        applySettings(settings);
        if (!settings.has_api_key) {
          showSetup(true);
          return;
        }
      } catch (_) {
        /* ignore */
      }
    }
    showSetup(false);
    enableFocusTrap(main);
    promptInput.focus();
    promptInput.select();
  }

  async function optimize() {
    if (busy) return;
    const text = promptInput.value.trim();
    if (!text) return;

    const bridge = api();
    if (!bridge) {
      showError("App bridge not ready. Try again.");
      return;
    }

    setBusy(true);
    collapse();
    try {
      if (bridge.start_optimize) {
        const started = await bridge.start_optimize(text);
        if (!started || started.ok === false) {
          setBusy(false);
          showError((started && started.error) || "Could not start optimization.");
        }
        return;
      }

      const res = await bridge.optimize(text);
      if (res && res.ok) {
        showResult(res.result, !!res.copied);
      } else {
        showError((res && res.error) || "Optimization failed.");
      }
      setBusy(false);
    } catch (err) {
      showError(err && err.message ? err.message : String(err));
      setBusy(false);
    }
  }

  function onOptimizeDone(res) {
    setBusy(false);
    if (res && res.ok) {
      showResult(res.result, !!res.copied);
    } else {
      showError((res && res.error) || "Optimization failed.");
    }
    promptInput.focus();
  }

  async function hideWindow() {
    disableFocusTrap();
    const bridge = api();
    if (bridge && bridge.hide) {
      try {
        await bridge.hide();
      } catch (_) {
        /* ignore */
      }
    }
  }

  function onEscape(e) {
    if (e.key !== "Escape") return;
    const dialog = getActiveDialog();
    if (!dialog) return;
    e.preventDefault();
    hideWindow();
  }

  // ── Events ──

  promptInput.addEventListener("input", autosizeInput);

  promptInput.addEventListener("paste", () => {
    setTimeout(autosizeInput, 0);
  });

  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      optimize();
    }
  });

  document.addEventListener("keydown", onEscape);

  // Dismiss when the webview loses focus — not on clicks inside the dialog
  window.addEventListener("blur", () => {
    setTimeout(() => {
      if (!document.hasFocus()) {
        hideWindow();
      }
    }, 140);
  });

  modeBadge.addEventListener("click", async () => {
    if (busy) return;
    const next = mode === "fast" ? "thorough" : "fast";
    const bridge = api();
    if (!bridge || !bridge.set_mode) return;
    try {
      const res = await bridge.set_mode(next);
      if (res && res.ok) {
        mode = next;
        updateModeBadge();
      }
    } catch (_) {
      /* ignore */
    }
  });

  copyBtn.addEventListener("click", async () => {
    const bridge = api();
    const text = resultText.value;
    if (bridge && bridge.copy_text) {
      await bridge.copy_text(text);
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    }
    copiedHint.classList.add("show");
    setTimeout(() => copiedHint.classList.remove("show"), 1800);
  });

  resultText.addEventListener("focus", () => {
    resultText.removeAttribute("readonly");
  });

  saveKeyBtn.addEventListener("click", async () => {
    setupError.classList.add("hidden");
    const bridge = api();
    if (!bridge || !bridge.save_api_key) {
      setupError.textContent = "App bridge not ready.";
      setupError.classList.remove("hidden");
      return;
    }
    const res = await bridge.save_api_key(apiKeyInput.value);
    if (res && res.ok) {
      apiKeyInput.value = "";
      showSetup(false);
      promptInput.focus();
    } else {
      setupError.textContent = (res && res.error) || "Could not save key.";
      setupError.classList.remove("hidden");
    }
  });

  apiKeyInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      saveKeyBtn.click();
    }
  });

  // Keep dialog centered in the viewport on resize (CSS flex handles this;
  // this hook is for any future JS layout adjustments)
  window.addEventListener("resize", () => {
    autosizeInput();
  });

  window.metaPrompt = {
    onShown,
    reset,
    collapse,
    onOptimizeDone,
  };

  window.addEventListener("pywebviewready", onShown);
  if (window.pywebview) {
    onShown();
  }
})();
