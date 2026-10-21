/**
 * FilePetal Website Client Script
 * Fetches latest public GitHub Release, updates download links & counts,
 * detects visitor operating system, handles theme switching and FAQ toggles.
 */

(function () {
  "use strict";

  // Known fallback release data (v1.11.1) if API is unavailable or rate-limited
  const FALLBACK_RELEASE = {
    tag_name: "v1.11.1",
    html_url: "https://github.com/Whatthefook/FilePetal/releases/tag/v1.11.1",
    assets: [
      {
        name: "FilePetal-1.11.1-windows-x64.zip",
        browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-windows-x64.zip",
        download_count: null
      },
      {
        name: "FilePetal-1.11.1-macos-arm64.zip",
        browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-macos-arm64.zip",
        download_count: null
      },
      {
        name: "FilePetal-1.11.1-macos-x64.zip",
        browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-macos-x64.zip",
        download_count: null
      },
      {
        name: "FilePetal-1.11.1-linux-x64.zip",
        browser_download_url: "https://github.com/Whatthefook/FilePetal/releases/download/v1.11.1/FilePetal-1.11.1-linux-x64.zip",
        download_count: null
      }
    ]
  };

  const API_URL = "https://api.github.com/repos/Whatthefook/FilePetal/releases/latest";
  const CACHE_KEY = "filepetal_release_cache_v1";
  const CACHE_TTL_MS = 15 * 60 * 1000; // 15 minutes TTL

  // Asset matcher
  function matchPlatformAsset(assets, platform) {
    if (!Array.isArray(assets)) return null;

    return assets.find(function (item) {
      const name = (item.name || "").toLowerCase();
      if (!name.endsWith(".zip")) return false;

      switch (platform) {
        case "windows-x64":
          return name.includes("windows") && name.includes("x64");
        case "macos-arm64":
          return name.includes("macos") && (name.includes("arm64") || name.includes("aarch64"));
        case "macos-x64":
          return name.includes("macos") && (name.includes("x64") || name.includes("intel") || name.includes("x86_64"));
        case "linux-x64":
          return name.includes("linux") && name.includes("x64");
        default:
          return false;
      }
    });
  }

  // Update DOM with release data
  function applyReleaseData(release, isLive) {
    const tagName = release.tag_name || "v1.11.1";
    const releaseUrl = release.html_url || "https://github.com/Whatthefook/FilePetal/releases/latest";

    // Badges in header & hero
    const navBadge = document.getElementById("nav-release-badge");
    if (navBadge) navBadge.textContent = tagName;

    const heroVersionTag = document.getElementById("hero-version-tag");
    if (heroVersionTag) {
      heroVersionTag.textContent = tagName;
      heroVersionTag.href = releaseUrl;
    }

    // Status indicator
    const indicatorDot = document.getElementById("api-indicator-dot");
    const statusText = document.getElementById("api-status-text");

    if (indicatorDot && statusText) {
      if (isLive) {
        indicatorDot.className = "status-indicator live";
        statusText.textContent = "Latest Release " + tagName + " (live from GitHub)";
      } else {
        indicatorDot.className = "status-indicator fallback";
        statusText.textContent = "Release " + tagName + " (verified offline fallback links)";
      }
    }

    // Update 4 download targets
    const targets = [
      { key: "windows-x64", btnId: "btn-windows", nameId: "name-windows", countId: "count-windows" },
      { key: "macos-arm64", btnId: "btn-macos-arm64", nameId: "name-macos-arm64", countId: "count-macos-arm64" },
      { key: "macos-x64", btnId: "btn-macos-x64", nameId: "name-macos-x64", countId: "count-macos-x64" },
      { key: "linux-x64", btnId: "btn-linux", nameId: "name-linux", countId: "count-linux" }
    ];

    targets.forEach(function (t) {
      let asset = matchPlatformAsset(release.assets, t.key);

      // If not found in live assets, fall back to known matching asset
      if (!asset) {
        asset = matchPlatformAsset(FALLBACK_RELEASE.assets, t.key);
      }

      if (!asset) return;

      const btn = document.getElementById(t.btnId);
      if (btn && asset.browser_download_url) {
        btn.href = asset.browser_download_url;
      }

      const nameEl = document.getElementById(t.nameId);
      if (nameEl && asset.name) {
        nameEl.textContent = asset.name;
      }

      const countEl = document.getElementById(t.countId);
      if (countEl) {
        if (typeof asset.download_count === "number") {
          countEl.textContent = asset.download_count.toLocaleString() + " downloads";
          countEl.classList.remove("count-unavailable");
        } else {
          // Exact neutral message required when API is unavailable or unpopulated
          countEl.textContent = "Download count unavailable";
          countEl.classList.add("count-unavailable");
        }
      }
    });
  }

  // Fetch with cache and fallback
  function loadReleaseData() {
    let cached = null;
    try {
      const stored = sessionStorage.getItem(CACHE_KEY) || localStorage.getItem(CACHE_KEY);
      if (stored) {
        cached = JSON.parse(stored);
      }
    } catch (_err) {
      // Storage access blocked or restricted
    }

    const now = Date.now();
    if (cached && cached.timestamp && (now - cached.timestamp < CACHE_TTL_MS) && cached.data) {
      applyReleaseData(cached.data, true);
      return;
    }

    // Perform network request with timeout
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(function () { controller.abort(); }, 7000) : null;

    fetch(API_URL, {
      headers: { "Accept": "application/vnd.github.v3+json" },
      signal: controller ? controller.signal : undefined
    })
      .then(function (res) {
        if (timeoutId) clearTimeout(timeoutId);
        if (!res.ok) {
          throw new Error("GitHub API responded with status " + res.status);
        }
        return res.json();
      })
      .then(function (data) {
        applyReleaseData(data, true);
        try {
          const payload = JSON.stringify({ timestamp: Date.now(), data: data });
          sessionStorage.setItem(CACHE_KEY, payload);
        } catch (_e) {
          // Ignore cache save error
        }
      })
      .catch(function (error) {
        console.warn("FilePetal release fetch failed, using fallback:", error.message);
        if (cached && cached.data) {
          applyReleaseData(cached.data, false);
        } else {
          applyReleaseData(FALLBACK_RELEASE, false);
        }
      });
  }

  // OS Detection & Recommendation
  function detectOS() {
    const userAgent = (navigator.userAgent || "").toLowerCase();
    const platform = (navigator.platform || "").toLowerCase();

    const isWindows = userAgent.includes("win") || platform.includes("win");
    const isMac = userAgent.includes("mac") || platform.includes("mac");
    const isLinux = (userAgent.includes("linux") || platform.includes("linux")) && !userAgent.includes("android");

    if (isWindows) {
      highlightPlatform("windows");
    } else if (isMac) {
      highlightPlatform("macos");
      // Check Apple Silicon hint if available via WebGL or userAgentData
      detectMacArchitecture();
    } else if (isLinux) {
      highlightPlatform("linux");
    }
  }

  function highlightPlatform(platformId) {
    const card = document.getElementById("card-" + platformId);
    if (card) {
      card.classList.add("detected-system");
    }
    const badge = document.getElementById("rec-" + platformId);
    if (badge) {
      badge.hidden = false;
    }
  }

  function detectMacArchitecture() {
    // navigator.userAgentData hints (Chromium on Mac)
    if (navigator.userAgentData && typeof navigator.userAgentData.getHighEntropyValues === "function") {
      navigator.userAgentData.getHighEntropyValues(["architecture"])
        .then(function (values) {
          if (values.architecture === "arm") {
            markMacChoice("arm64");
          } else if (values.architecture === "x86") {
            markMacChoice("x64");
          }
        })
        .catch(function () {});
    }
  }

  function markMacChoice(arch) {
    const pill = document.getElementById("rec-macos-" + arch);
    if (pill) pill.hidden = false;
    const parentBox = pill ? pill.closest(".mac-option-box") : null;
    if (parentBox) parentBox.classList.add("active-mac");
  }

  // Theme Toggle (Dark / Light)
  function initTheme() {
    const toggleBtn = document.getElementById("theme-toggle");
    if (!toggleBtn) return;

    let savedTheme = null;
    try {
      savedTheme = localStorage.getItem("filepetal_theme");
    } catch (_e) {}

    function applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      toggleBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      toggleBtn.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
      const themeColor = document.querySelector('meta[name="theme-color"]');
      if (themeColor) themeColor.setAttribute("content", theme === "dark" ? "#202621" : "#f6f3eb");
    }

    applyTheme(savedTheme === "dark" ? "dark" : "light");

    toggleBtn.addEventListener("click", function () {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem("filepetal_theme", next);
      } catch (_e) {}
    });
  }

  // Browser-only radial wheel preview. Sample files are labels and never leave this page.
  const DEMO_SAMPLES = {
    image: {
      name: "coast.jpg",
      type: "IMAGE",
      outputs: [["WEBP", "smaller web image"], ["PNG", "lossless image"], ["PDF", "document"], ["DOCX", "editable page"]]
    },
    markdown: {
      name: "README.md",
      type: "MARKDOWN",
      outputs: [["HTML", "web page"], ["PDF", "document"], ["TXT", "plain text"], ["PNG", "page image"]]
    },
    pdf: {
      name: "brief.pdf",
      type: "PDF",
      outputs: [["DOCX", "editable text"], ["TXT", "plain text"], ["PNG", "page image"], ["JPG", "page image"]]
    },
    video: {
      name: "walkthrough.mp4",
      type: "VIDEO",
      outputs: [["GIF", "animation"], ["WEBM", "video"], ["MOV", "video"], ["MP3", "audio track"]]
    },
    audio: {
      name: "voice-note.wav",
      type: "AUDIO",
      outputs: [["MP3", "compressed audio"], ["M4A", "audio"], ["OGG", "audio"], ["FLAC", "lossless audio"]]
    }
  };

  function initDemo() {
    const stage = document.getElementById("demo-stage");
    const wheel = document.getElementById("demo-wheel");
    const petals = document.getElementById("demo-petals");
    const modeLabel = document.getElementById("demo-mode-label");
    const centerType = document.getElementById("demo-center-type");
    const centerName = document.getElementById("demo-center-name");
    const resultTitle = document.getElementById("demo-result-title");
    const resultCopy = document.getElementById("demo-result-copy");
    const resetButton = document.getElementById("demo-reset");
    const sampleButtons = Array.from(document.querySelectorAll(".demo-file[data-sample]"));
    if (!stage || !wheel || !petals || !sampleButtons.length) return;

    let activeSampleKey = null;
    let draggingSampleKey = null;
    let droppedInStage = false;

    function setResult(title, copy) {
      if (resultTitle) resultTitle.textContent = title;
      if (resultCopy) resultCopy.textContent = copy;
    }

    function outputName(filename, extension) {
      const dot = filename.lastIndexOf(".");
      const base = dot > 0 ? filename.slice(0, dot) : filename;
      return base + "." + extension.toLowerCase();
    }

    function previewOutput(sample, format, button) {
      const destination = outputName(sample.name, format);
      petals.querySelectorAll(".demo-petal").forEach(function (petal) {
        petal.classList.toggle("is-active", petal === button);
        petal.setAttribute("aria-pressed", petal === button ? "true" : "false");
      });
      if (modeLabel) modeLabel.textContent = "Preview: " + format;
      setResult("Output preview", destination + " would be saved beside " + sample.name + " in the desktop app. This browser preview does not create a file.");
    }

    function selectSample(key, source) {
      const sample = DEMO_SAMPLES[key];
      if (!sample) return;
      activeSampleKey = key;
      sampleButtons.forEach(function (button) {
        const selected = button.dataset.sample === key;
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      });
      stage.classList.add("has-file");
      wheel.hidden = false;
      if (centerType) centerType.textContent = sample.type;
      if (centerName) centerName.textContent = sample.name;
      if (modeLabel) modeLabel.textContent = source === "drag" ? "File picked up" : "Choose an output";
      if (resetButton) resetButton.hidden = false;
      petals.replaceChildren();

      sample.outputs.forEach(function (output) {
        const format = output[0];
        const note = output[1];
        const petal = document.createElement("button");
        petal.type = "button";
        petal.className = "demo-petal";
        petal.setAttribute("aria-pressed", "false");
        petal.setAttribute("aria-label", "Preview " + sample.name + " converted to " + format);

        const formatLabel = document.createElement("span");
        formatLabel.className = "demo-petal-format";
        formatLabel.textContent = format;
        const noteLabel = document.createElement("span");
        noteLabel.className = "demo-petal-note";
        noteLabel.textContent = note;
        petal.append(formatLabel, noteLabel);
        petal.addEventListener("click", function () { previewOutput(sample, format, petal); });
        petals.appendChild(petal);
      });

      setResult("Choose a petal", "Four compatible output previews are ready for " + sample.name + ". Select one to see the result name.");
    }

    function resetDemo() {
      activeSampleKey = null;
      draggingSampleKey = null;
      droppedInStage = false;
      sampleButtons.forEach(function (button) {
        button.classList.remove("is-selected", "is-dragging");
        button.setAttribute("aria-pressed", "false");
      });
      stage.classList.remove("has-file", "is-dragover");
      wheel.hidden = true;
      petals.replaceChildren();
      if (modeLabel) modeLabel.textContent = "Waiting for a file";
      if (resetButton) resetButton.hidden = true;
      setResult("Try a sample file", "Click or drag one from the left. Nothing is uploaded or changed.");
    }

    sampleButtons.forEach(function (button) {
      const key = button.dataset.sample;
      button.addEventListener("click", function () { selectSample(key, "click"); });
      button.addEventListener("dragstart", function (event) {
        draggingSampleKey = key;
        droppedInStage = false;
        button.classList.add("is-dragging");
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "copy";
          event.dataTransfer.setData("text/plain", "filepetal-demo:" + key);
        }
        selectSample(key, "drag");
      });
      button.addEventListener("dragend", function () {
        button.classList.remove("is-dragging");
        stage.classList.remove("is-dragover");
        if (!droppedInStage && activeSampleKey === key && modeLabel) modeLabel.textContent = "Preview ready";
        draggingSampleKey = null;
      });
    });

    stage.addEventListener("dragover", function (event) {
      if (!draggingSampleKey && !(event.dataTransfer && Array.from(event.dataTransfer.types || []).includes("Files"))) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
      stage.classList.add("is-dragover");
      if (draggingSampleKey && draggingSampleKey !== activeSampleKey) selectSample(draggingSampleKey, "drag");
    });
    stage.addEventListener("dragleave", function (event) {
      if (!stage.contains(event.relatedTarget)) stage.classList.remove("is-dragover");
    });
    stage.addEventListener("drop", function (event) {
      if (draggingSampleKey) {
        event.preventDefault();
        droppedInStage = true;
        selectSample(draggingSampleKey, "drop");
        if (modeLabel) modeLabel.textContent = "Choose an output";
        setResult("File on the wheel", "Choose one of the petals to preview its output. The sample remains a mockup.");
      } else if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
        event.preventDefault();
        setResult("Sample files only", "This browser demo does not read local files. Pick one of the five sample icons instead.");
      }
      stage.classList.remove("is-dragover");
    });

    if (resetButton) resetButton.addEventListener("click", resetDemo);
  }

  // Document ready initializer
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  function init() {
    initTheme();
    detectOS();
    initDemo();
    loadReleaseData();
  }
})();
