/* FilePetal website interactions. The desktop demo uses mock files only. */
(function () {
  "use strict";

  const FALLBACK_RELEASE = {
    tag_name: "v1.11.1",
    html_url: "https://github.com/Whatthefook/FilePetal/releases/tag/v1.11.1",
    assets: [
      { name: "FilePetal-1.11.1-windows-x64.zip", browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-windows-x64.zip" },
      { name: "FilePetal-1.11.1-macos-arm64.zip", browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-macos-arm64.zip" },
      { name: "FilePetal-1.11.1-macos-x64.zip", browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-macos-x64.zip" },
      { name: "FilePetal-1.11.1-linux-x64.zip", browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-linux-x64.zip" }
    ]
  };
  const API_URL = "https://api.github.com/repos/Whatthefook/FilePetal/releases/latest";
  const CACHE_KEY = "filepetal_release_cache_v1";
  const CACHE_TTL_MS = 15 * 60 * 1000;

  const SAMPLE_FILES = {
    image: { name: "sunset.jpg", kind: "IMAGE", outputs: ["WEBP", "PNG", "PDF", "DOCX"], tools: ["Compress image", "Metadata", "Edit photo", "Annotate", "Add background", "Crop", "Redact", "Create PDF", "Create collage", "Read QR codes"] },
    markdown: { name: "README.md", kind: "MARKDOWN", outputs: ["HTML", "PDF", "TXT", "PNG"], tools: [] },
    pdf: { name: "brief.pdf", kind: "PDF", outputs: ["DOCX", "TXT", "PNG", "JPG"], tools: ["Compress PDF", "Split pages", "Merge PDFs", "Read QR codes"] },
    video: { name: "clip.mp4", kind: "VIDEO", outputs: ["WEBM", "MOV", "GIF", "MP3"], tools: ["Compress video", "Metadata", "Remove audio", "Trim", "Crop", "Change speed", "Snapshots", "Split", "Redact", "Join videos"] },
    audio: { name: "voice.wav", kind: "AUDIO", outputs: ["MP3", "M4A", "OGG", "FLAC"], tools: ["Compress audio", "Metadata", "Normalize", "Trim", "Channels", "Bleep section", "Waveform video"] }
  };
  const ACTIONS = ["Float shelf", "Copy files", "Move to folder", "Copy path", "Open in terminal", "Share"];
  const MODES = {
    convert: { label: "CONVERT", shortcut: "SHIFT", title: "Choose an output format" },
    tools: { label: "TOOLS", shortcut: "ALT + SHIFT", title: "Choose a tool" },
    actions: { label: "ACTIONS", shortcut: "CTRL + SHIFT", title: "Choose a file action" }
  };

  function safeRead(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }
  function safeWrite(key, value) { try { localStorage.setItem(key, value); } catch (_) {} }

  function initTheme() {
    const button = document.getElementById("theme-toggle");
    const root = document.documentElement;
    if (!button) return;
    function apply(theme) {
      root.setAttribute("data-theme", theme);
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
      const color = document.querySelector('meta[name="theme-color"]');
      if (color) color.content = theme === "dark" ? "#20231f" : "#f2f0e9";
    }
    apply(safeRead("filepetal_theme") === "dark" ? "dark" : "light");
    button.addEventListener("click", function () {
      const theme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(theme);
      safeWrite("filepetal_theme", theme);
    });
  }

  function matchAsset(assets, key) {
    if (!Array.isArray(assets)) return null;
    return assets.find(function (asset) {
      const name = (asset.name || "").toLowerCase();
      if (!name.endsWith(".zip")) return false;
      if (key === "windows-x64") return name.includes("windows") && name.includes("x64");
      if (key === "macos-arm64") return name.includes("macos") && (name.includes("arm64") || name.includes("aarch64"));
      if (key === "macos-x64") return name.includes("macos") && (name.includes("x64") || name.includes("intel") || name.includes("x86_64"));
      return name.includes("linux") && name.includes("x64");
    });
  }

  function initReleaseData() {
    const status = document.getElementById("api-status-text");
    if (!status) return;
    let cached = null;
    try { cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null"); } catch (_) {}
    function render(release, live) {
      const tag = release.tag_name || "latest release";
      const dot = document.getElementById("api-indicator-dot");
      status.textContent = live ? "Latest release " + tag + " · live from GitHub" : "Release " + tag + " · showing saved package links";
      if (dot) dot.className = "status-indicator " + (live ? "live" : "fallback");
      [
        ["windows-x64", "windows"], ["macos-arm64", "macos-arm64"],
        ["macos-x64", "macos-x64"], ["linux-x64", "linux"]
      ].forEach(function (pair) {
        const asset = matchAsset(release.assets, pair[0]) || matchAsset(FALLBACK_RELEASE.assets, pair[0]);
        if (!asset) return;
        const suffix = pair[1];
        const button = document.getElementById("btn-" + suffix);
        const filename = document.getElementById("name-" + suffix);
        const count = document.getElementById("count-" + suffix);
        if (button) button.href = asset.browser_download_url;
        if (filename) filename.textContent = asset.name;
        if (count) {
          count.textContent = Number.isFinite(asset.download_count) ? asset.download_count.toLocaleString() + " downloads" : "Download count unavailable";
          count.classList.toggle("count-unavailable", !Number.isFinite(asset.download_count));
        }
      });
    }
    const fresh = cached && cached.timestamp && Date.now() - cached.timestamp < CACHE_TTL_MS;
    if (fresh) render(cached.data, true);
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = controller ? window.setTimeout(function () { controller.abort(); }, 6500) : null;
    fetch(API_URL, { headers: { Accept: "application/vnd.github+json" }, signal: controller ? controller.signal : undefined })
      .then(function (response) { if (!response.ok) throw new Error("GitHub returned " + response.status); return response.json(); })
      .then(function (release) {
        if (timer) clearTimeout(timer);
        render(release, true);
        try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ timestamp: Date.now(), data: release })); } catch (_) {}
      })
      .catch(function () {
        if (timer) clearTimeout(timer);
        if (!fresh) render(cached && cached.data ? cached.data : FALLBACK_RELEASE, false);
      });
  }

  function initPlatformHint() {
    const ua = (navigator.userAgent || "").toLowerCase();
    const platform = (navigator.platform || "").toLowerCase();
    if (ua.includes("windows") || platform.includes("win")) show("windows");
    else if (ua.includes("mac") || platform.includes("mac")) show("macos");
    else if ((ua.includes("linux") || platform.includes("linux")) && !ua.includes("android")) show("linux");
    function show(id) {
      const card = document.getElementById("card-" + id);
      const badge = document.getElementById("rec-" + id);
      if (card) card.classList.add("detected-system");
      if (badge) badge.hidden = false;
    }
  }

  function initFaq() {
    const items = Array.from(document.querySelectorAll(".faq-item"));
    items.forEach(function (item) {
      item.addEventListener("toggle", function () {
        if (!item.open) return;
        items.forEach(function (other) { if (other !== item) other.open = false; });
      });
    });
  }

  function initDesktopDemo() {
    const stage = document.getElementById("desktop-stage");
    if (!stage) return;
    const wheel = document.getElementById("gesture-wheel");
    const petals = document.getElementById("wheel-options");
    const modeName = document.getElementById("wheel-mode");
    const filename = document.getElementById("wheel-filename");
    const toast = document.getElementById("desktop-toast");
    const feedback = document.getElementById("demo-feedback");
    const files = Array.from(stage.querySelectorAll(".desktop-file"));
    const previewButtons = Array.from(document.querySelectorAll(".shortcut-button"));
    let selected = null;
    let armed = null;
    let dragging = null;
    let dragOrigin = null;
    let liveMode = null;
    let lastPointer = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const startPositions = new Map();

    function say(message, detail) {
      if (toast) toast.textContent = message;
      if (feedback && detail) feedback.textContent = detail;
    }
    function setSelected(file, isArmed) {
      selected = file;
      files.forEach(function (el) {
        const active = el === file;
        el.classList.toggle("is-selected", active);
        el.setAttribute("aria-pressed", String(active));
      });
      if (isArmed) {
        armed = file;
        file.classList.add("is-armed");
        say(file.dataset.name + " picked up. Drag it, then hold a shortcut.", "Picked up " + file.dataset.name + ". Drag inside the desktop and hold Shift, Alt + Shift, or Ctrl + Shift.");
      }
    }
    function modeFromKeys(event) {
      if (!event.shiftKey) return null;
      if (event.ctrlKey) return "actions";
      if (event.altKey) return "tools";
      return "convert";
    }
    function formatOutputName(name, extension) {
      return name.replace(/\.[^.]+$/, "") + "." + extension.toLowerCase();
    }
    function moveWheel(clientX, clientY) {
      const bounds = stage.getBoundingClientRect();
      const size = wheel.offsetWidth || Math.min(310, bounds.width - 20);
      const x = Math.max(size / 2 + 8, Math.min(bounds.width - size / 2 - 8, clientX - bounds.left));
      const header = document.querySelector(".site-header");
      const topEdge = Math.max(size / 2 + 8, (header ? header.getBoundingClientRect().bottom : 0) + size / 2 + 8 - bounds.top);
      const bottomEdge = Math.min(bounds.height - size / 2 - 8, window.innerHeight - size / 2 - 8 - bounds.top);
      const minY = Math.min(topEdge, bottomEdge);
      const maxY = Math.max(topEdge, bottomEdge);
      const y = Math.max(minY, Math.min(maxY, clientY - bounds.top));
      wheel.style.setProperty("--wheel-x", x + "px");
      wheel.style.setProperty("--wheel-y", y + "px");
    }
    function closeWheel() {
      if (!wheel) return;
      wheel.hidden = true;
      liveMode = null;
      stage.classList.remove("wheel-open");
      previewButtons.forEach(function (button) { button.setAttribute("aria-pressed", "false"); });
    }
    function showWheel(mode, file, clientX, clientY) {
      const sample = SAMPLE_FILES[file.dataset.file];
      if (!sample || !wheel || !petals) return;
      liveMode = mode;
      const config = MODES[mode];
      const choices = mode === "convert" ? sample.outputs : mode === "tools" ? sample.tools : ACTIONS;
      const diameter = window.matchMedia("(max-width: 680px)").matches ? Math.min(290, window.innerWidth - 44) : Math.min(310, stage.clientWidth - 20);
      const radius = Math.max(76, diameter / 2 - 48);
      petals.replaceChildren();
      if (modeName) modeName.textContent = config.label;
      if (filename) filename.textContent = sample.name;
      choices.forEach(function (label, index) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "wheel-petal";
        button.style.setProperty("--petal-index", index);
        const angle = (Math.PI * 2 * index / choices.length) - Math.PI / 2;
        button.style.left = "calc(50% + " + Math.cos(angle) * radius + "px)";
        button.style.top = "calc(50% + " + Math.sin(angle) * radius + "px)";
        button.style.maxWidth = choices.length > 8 ? "72px" : choices.length > 4 ? "82px" : "92px";
        button.textContent = label;
        button.setAttribute("aria-label", mode === "convert" ? "Preview conversion to " + label : "Preview " + label);
        button.addEventListener("click", function () {
          const message = mode === "convert"
            ? formatOutputName(sample.name, label) + " would be saved beside the source file. This demo does not create it."
            : mode === "tools"
              ? label + " would open in FilePetal. The demo does not edit the sample."
              : label + " would run on the selected file in the desktop app. This demo does not perform the action.";
          say(label + " selected", message);
          closeWheel();
        });
        petals.appendChild(button);
      });
      if (!choices.length) {
        const empty = document.createElement("p");
        empty.className = "wheel-empty";
        empty.textContent = "No dedicated tool for Markdown files";
        petals.appendChild(empty);
      }
      wheel.hidden = false;
      stage.classList.add("wheel-open");
      if (Number.isFinite(clientX) && Number.isFinite(clientY)) moveWheel(clientX, clientY);
      const control = previewButtons.find(function (button) { return button.dataset.mode === mode; });
      previewButtons.forEach(function (button) { button.setAttribute("aria-pressed", String(button === control)); });
      if (mode === "convert") say(config.shortcut + " · " + sample.name, "Convert preview for " + sample.name + ". Hold the shortcut while dragging; select a format to preview its output name.");
      else if (mode === "tools") say(config.shortcut + " · " + sample.name, sample.tools.length ? "Tools available for " + sample.name + ". Select a tool to see what would open." : "This file type has no dedicated tool in the current app; its conversion wheel still works.");
      else say(config.shortcut + " · " + sample.name, "The app’s file actions apply to this selected sample. This page previews labels only.");
    }

    function reset() {
      closeWheel();
      dragging = null;
      dragOrigin = null;
      armed = null;
      selected = null;
      files.forEach(function (file) {
        file.classList.remove("is-selected", "is-armed", "is-dragging");
        file.removeAttribute("style");
        file.setAttribute("aria-pressed", "false");
      });
      startPositions.clear();
      say("Double-click a sample icon to pick it up.", "This is a visual preview only. It does not read, upload, or change local files.");
    }

    files.forEach(function (file) {
      file.dataset.name = file.querySelector("span").textContent;
      file.addEventListener("click", function () { if (!dragging) setSelected(file, false); });
      file.addEventListener("dblclick", function (event) {
        event.preventDefault();
        file.classList.remove("is-armed");
        setSelected(file, true);
      });
      file.addEventListener("pointerdown", function (event) {
        if (event.button !== 0 || armed !== file) return;
        dragging = file;
        lastPointer = { x: event.clientX, y: event.clientY };
        dragOrigin = { x: event.clientX, y: event.clientY, left: file.offsetLeft, top: file.offsetTop };
        const stageRect = stage.getBoundingClientRect();
        const fileRect = file.getBoundingClientRect();
        startPositions.set(file, { left: fileRect.left - stageRect.left, top: fileRect.top - stageRect.top });
        file.classList.add("is-dragging");
        event.preventDefault();
      });
      function moveFile(event) {
        if (dragging !== file || !dragOrigin) return;
        lastPointer = { x: event.clientX, y: event.clientY };
        const dx = event.clientX - dragOrigin.x;
        const dy = event.clientY - dragOrigin.y;
        if (Math.hypot(dx, dy) > 3) file.classList.add("has-moved");
        const stageRect = stage.getBoundingClientRect();
        const fileRect = file.getBoundingClientRect();
        const width = stage.clientWidth;
        const height = stage.clientHeight;
        const origin = startPositions.get(file);
        const nextLeft = Math.max(4, Math.min(width - fileRect.width - 4, origin.left + dx));
        const nextTop = Math.max(4, Math.min(height - fileRect.height - 4, origin.top + dy));
        file.style.left = nextLeft + "px";
        file.style.top = nextTop + "px";
        file.style.setProperty("--drag-x", "0px");
        const mode = modeFromKeys(event);
        if (mode) showWheel(mode, file, event.clientX, event.clientY);
        else if (liveMode) closeWheel();
      }
      window.addEventListener("pointermove", moveFile);
      function endDrag() {
        if (dragging !== file) return;
        file.classList.remove("is-dragging", "has-moved");
        const modeAtDrop = liveMode;
        dragging = null;
        dragOrigin = null;
        armed = null;
        file.classList.remove("is-armed");
        if (modeAtDrop) say("" + MODES[modeAtDrop].label + " wheel ready", "Select an option from the wheel to preview what the desktop app would do.");
        else say("File placed on the desktop.", "Your sample icon moved. Hold a modifier shortcut during the drag to open a wheel.");
      }
      file.addEventListener("dragstart", function (event) { event.preventDefault(); });
      window.addEventListener("pointerup", endDrag);
      window.addEventListener("pointercancel", endDrag);
    });

    window.addEventListener("keydown", function (event) {
      if (!dragging) return;
      const mode = modeFromKeys(event);
      if (mode) showWheel(mode, dragging, lastPointer.x, lastPointer.y);
    });
    window.addEventListener("keyup", function (event) {
      if (!liveMode) return;
      if (!event.shiftKey || liveMode === "tools" && !event.altKey || liveMode === "actions" && !event.ctrlKey) closeWheel();
    });
    previewButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        const file = selected || files[0];
        setSelected(file, false);
        const rect = file.getBoundingClientRect();
        showWheel(button.dataset.mode, file, rect.left + rect.width / 2, rect.top + rect.height / 2);
      });
    });
    const resetButton = document.getElementById("demo-reset");
    if (resetButton) resetButton.addEventListener("click", reset);
    stage.addEventListener("pointerdown", function (event) {
      if (event.target === stage && !dragging) {
        closeWheel();
        files.forEach(function (file) { file.classList.remove("is-selected"); file.setAttribute("aria-pressed", "false"); });
        selected = null;
      }
    });
  }

  function init() {
    initTheme();
    initReleaseData();
    initPlatformHint();
    initFaq();
    initDesktopDemo();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
