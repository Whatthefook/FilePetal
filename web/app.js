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

    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const activeTheme = savedTheme || (prefersDark ? "dark" : "dark"); // Default dark matches brand

    document.documentElement.setAttribute("data-theme", activeTheme);

    toggleBtn.addEventListener("click", function () {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("filepetal_theme", next);
      } catch (_e) {}
    });

    // Listen for OS scheme change if user hasn't set manual preference
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
      let userOverride = null;
      try {
        userOverride = localStorage.getItem("filepetal_theme");
      } catch (_e) {}
      if (!userOverride) {
        document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
      }
    });
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
    loadReleaseData();
  }
})();
