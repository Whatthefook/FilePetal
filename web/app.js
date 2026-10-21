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
    tools: { label: "TOOLS", shortcut: "ALT + SHIFT / CTRL + ALT", title: "Choose a tool" },
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
          count.textContent = Number.isFinite(asset.download_count) ? asset.download_count.toLocaleString() + (asset.download_count === 1 ? " download" : " downloads") : "Download count unavailable";
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
    let selected = null;
    let dragging = null;
    let dragOrigin = null;
    let activePointerId = null;
    let liveMode = null;
    let wheelPinned = false;
    let renderedWheelKey = null;
    let lastPointer = { x: 0, y: 0 };

    function say(message, detail) {
      if (toast) toast.textContent = message;
      if (feedback && detail) feedback.textContent = detail;
    }
    function setSelected(file) {
      selected = file;
      files.forEach(function (el) {
        const active = el === file;
        el.classList.toggle("is-selected", active);
        el.setAttribute("aria-pressed", String(active));
      });
    }
    function modeFromKeys(event) {
      if (event.ctrlKey && event.shiftKey) return "actions";
      if ((event.altKey && event.shiftKey) || (event.ctrlKey && event.altKey)) return "tools";
      if (event.shiftKey) return "convert";
      return null;
    }
    function formatOutputName(name, extension) {
      return name.replace(/\.[^.]+$/, "") + "." + extension.toLowerCase();
    }
    function placeWheel(clientX, clientY) {
      const bounds = stage.getBoundingClientRect();
      const size = wheel.offsetWidth || 300;
      const half = size / 2;
      const x = Math.max(half + 8, Math.min(bounds.width - half - 8, clientX - bounds.left));
      const header = document.querySelector(".site-header");
      const headerBottom = header ? header.getBoundingClientRect().bottom : 0;
      const minY = Math.max(half + 4, headerBottom + half + 4 - bounds.top);
      const maxY = Math.min(bounds.height - half - 4, window.innerHeight - half - 4 - bounds.top);
      const pointerY = clientY - bounds.top;
      const y = minY <= maxY
        ? Math.max(minY, Math.min(maxY, pointerY))
        : Math.max(half + 4, Math.min(bounds.height - half - 4, pointerY));
      wheel.style.setProperty("--wheel-x", x + "px");
      wheel.style.setProperty("--wheel-y", y + "px");
    }
    function closeWheel() {
      if (!wheel) return;
      wheel.hidden = true;
      liveMode = null;
      wheelPinned = false;
      renderedWheelKey = null;
      stage.classList.remove("wheel-open");
    }
    function showWheel(mode, file, clientX, clientY, pin) {
      const sample = SAMPLE_FILES[file.dataset.file];
      if (!sample || !wheel || !petals) return;
      const renderKey = mode + ":" + file.dataset.file;
      const needsRender = renderedWheelKey !== renderKey || wheel.hidden;
      liveMode = mode;
      if (pin) wheelPinned = true;
      const config = MODES[mode];
      if (needsRender) {
        const choices = mode === "convert" ? sample.outputs : mode === "tools" ? sample.tools : ACTIONS;
        const diameter = Math.min(stage.clientWidth < 520 ? 260 : 280, Math.max(240, stage.clientWidth - 20));
        wheel.style.width = diameter + "px";
        const radius = Math.max(76, diameter / 2 - 48);
        petals.replaceChildren();
        if (modeName) modeName.textContent = config.label;
        if (filename) filename.textContent = sample.name;
        choices.forEach(function (label, index) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "wheel-petal";
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
          empty.textContent = "No dedicated tools for this file type";
          petals.appendChild(empty);
        }
        renderedWheelKey = renderKey;
      }
      wheel.hidden = false;
      stage.classList.add("wheel-open");
      if (Number.isFinite(clientX) && Number.isFinite(clientY)) placeWheel(clientX, clientY);
      if (needsRender) {
        if (mode === "convert") say(config.shortcut + " · " + sample.name, "Choose a format to preview the output filename. The demo does not create a file.");
        else if (mode === "tools") say(config.shortcut + " · " + sample.name, sample.tools.length ? "Choose a tool to preview what would open. The demo does not edit the sample." : "This file type has no dedicated tool here; its conversion wheel still works.");
        else say(config.shortcut + " · " + sample.name, "Choose an action to preview what the desktop app would do.");
      }
    }
    function startDrag(file, event) {
      if (wheelPinned) closeWheel();
      dragging = file;
      activePointerId = event.pointerId;
      const stageRect = stage.getBoundingClientRect();
      const fileRect = file.getBoundingClientRect();
      dragOrigin = { x: event.clientX, y: event.clientY, left: fileRect.left - stageRect.left, top: fileRect.top - stageRect.top };
      lastPointer = { x: event.clientX, y: event.clientY };
      file.classList.add("is-dragging");
      try { file.setPointerCapture(event.pointerId); } catch (_) {}
      event.preventDefault();
      const mode = modeFromKeys(event);
      if (mode) showWheel(mode, file, event.clientX, event.clientY, false);
      else say("Dragging " + file.dataset.name, "Hold Shift for Convert, Ctrl + Shift for Actions, or Ctrl + Alt (also Alt + Shift) for Tools.");
    }
    function moveFile(event) {
      if (!dragging || !dragOrigin || event.pointerId !== activePointerId) return;
      lastPointer = { x: event.clientX, y: event.clientY };
      const dx = event.clientX - dragOrigin.x;
      const dy = event.clientY - dragOrigin.y;
      if (Math.hypot(dx, dy) > 3) dragging.classList.add("has-moved");
      const bounds = stage.getBoundingClientRect();
      const fileRect = dragging.getBoundingClientRect();
      dragging.style.left = Math.max(4, Math.min(stage.clientWidth - fileRect.width - 4, dragOrigin.left + dx)) + "px";
      dragging.style.top = Math.max(4, Math.min(stage.clientHeight - fileRect.height - 4, dragOrigin.top + dy)) + "px";
      const mode = modeFromKeys(event);
      if (mode) showWheel(mode, dragging, event.clientX, event.clientY, false);
      else if (!wheelPinned && liveMode) closeWheel();
      const pointerOutside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
      if (pointerOutside && !wheelPinned) closeWheel();
    }
    function endDrag(event) {
      if (!dragging || event.pointerId !== activePointerId) return;
      const file = dragging;
      const didMove = file.classList.contains("has-moved");
      const modeAtDrop = liveMode;
      file.classList.remove("is-dragging", "has-moved");
      dragging = null;
      dragOrigin = null;
      activePointerId = null;
      if (didMove) {
        setSelected(file);
        if (modeAtDrop) {
          wheelPinned = true;
          say(MODES[modeAtDrop].label + " wheel ready", "The wheel stays open after you release the mouse. Click a petal to preview it.");
        } else {
          say("File placed on the desktop.", "The sample moved. Drag it again while holding a shortcut to open a wheel.");
        }
      } else {
        say(file.dataset.name + " selected", "Drag this sample and hold Shift, Ctrl + Shift, or Ctrl + Alt to open a wheel.");
      }
    }
    function reset() {
      closeWheel();
      dragging = null;
      dragOrigin = null;
      activePointerId = null;
      selected = null;
      files.forEach(function (file) {
        file.classList.remove("is-selected", "is-dragging", "has-moved");
        file.removeAttribute("style");
        file.setAttribute("aria-pressed", "false");
      });
      say("Drag any sample icon.", "This is a visual preview only. It does not read, upload, or change local files.");
    }

    files.forEach(function (file) {
      file.dataset.name = file.querySelector("span").textContent;
      file.addEventListener("pointerdown", function (event) {
        if (event.button !== 0) return;
        if (selected !== file && wheelPinned) closeWheel();
        setSelected(file);
        startDrag(file, event);
      });
      file.addEventListener("click", function (event) { event.preventDefault(); });
      file.addEventListener("dragstart", function (event) { event.preventDefault(); });
    });

    window.addEventListener("pointermove", moveFile);
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", endDrag);
    window.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeWheel();
        return;
      }
      if (!dragging) return;
      const mode = modeFromKeys(event);
      if (mode) showWheel(mode, dragging, lastPointer.x, lastPointer.y, false);
      else if (!wheelPinned) closeWheel();
    });
    window.addEventListener("keyup", function (event) {
      if (!dragging || wheelPinned) return;
      const mode = modeFromKeys(event);
      if (mode) showWheel(mode, dragging, lastPointer.x, lastPointer.y, false);
      else closeWheel();
    });
    window.addEventListener("blur", function () {
      if (dragging) endDrag({ pointerId: activePointerId });
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
