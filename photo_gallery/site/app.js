(() => {
  "use strict";

  const BATCH = 48;
  const gallery = document.getElementById("gallery");
  const sentinel = document.getElementById("sentinel");
  const countEl = document.getElementById("photo-count");
  const albumsNav = document.getElementById("albums");
  const lightbox = document.getElementById("lightbox");
  const lbImage = document.getElementById("lb-image");
  const lbCaption = document.getElementById("lb-caption");
  const lbClose = document.getElementById("lb-close");
  const lbPrev = document.getElementById("lb-prev");
  const lbNext = document.getElementById("lb-next");

  let photos = [];
  let filtered = [];
  let rendered = 0;
  let currentAlbum = "all";
  let currentIndex = -1;
  let lastTile = null;
  let observer = null;

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function tileHtml(photo) {
    const date = photo.date ? `<span class="tile-date">${escapeHtml(photo.date)}</span>` : "";
    return `
      <button class="tile" type="button" data-id="${escapeHtml(photo.id)}" aria-label="${escapeHtml(photo.title)}">
        <img src="${escapeHtml(photo.thumb)}" alt="${escapeHtml(photo.title)}"
          loading="lazy" decoding="async" width="${photo.width}" height="${photo.height}">
        <span class="tile-meta">
          <span class="tile-title">${escapeHtml(photo.title)}</span>
          ${date}
        </span>
      </button>`;
  }

  function buildAlbums() {
    const counts = new Map();
    for (const photo of photos) {
      counts.set(photo.album, (counts.get(photo.album) || 0) + 1);
    }
    const entries = [...counts.entries()].sort(
      (a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh")
    );
    for (const [album, count] of entries) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "album-pill";
      button.dataset.album = album;
      button.textContent = `${album} ${count}`;
      albumsNav.appendChild(button);
    }
  }

  function renderBatch() {
    if (rendered >= filtered.length) return;
    const end = Math.min(rendered + BATCH, filtered.length);
    const fragment = document.createDocumentFragment();
    const template = document.createElement("template");
    for (let i = rendered; i < end; i++) {
      template.innerHTML = tileHtml(filtered[i]).trim();
      fragment.appendChild(template.content.firstElementChild);
    }
    gallery.appendChild(fragment);
    rendered = end;
    sentinel.hidden = rendered >= filtered.length;
  }

  function ensureRendered(index) {
    while (rendered <= index && rendered < filtered.length) {
      renderBatch();
    }
  }

  function applyAlbum(album) {
    currentAlbum = album;
    filtered = album === "all" ? photos : photos.filter((p) => p.album === album);
    rendered = 0;
    gallery.replaceChildren();
    for (const button of albumsNav.querySelectorAll(".album-pill")) {
      button.classList.toggle("is-active", button.dataset.album === album);
    }
    if (!filtered.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "暂无照片";
      gallery.appendChild(empty);
      sentinel.hidden = true;
      return;
    }
    renderBatch();
  }

  function updateLightbox() {
    const photo = filtered[currentIndex];
    lbImage.src = photo.full;
    lbImage.alt = photo.title;
    const date = photo.date ? ` · ${photo.date}` : "";
    lbCaption.textContent = `${photo.title}${date} · ${currentIndex + 1} / ${filtered.length}`;
  }

  function openLightbox(index) {
    if (!filtered.length) return;
    currentIndex = index;
    updateLightbox();
    lightbox.hidden = false;
    document.body.classList.add("lock");
    lbClose.focus();
    history.replaceState(null, "", `#p-${filtered[currentIndex].id}`);
  }

  function closeLightbox() {
    lightbox.hidden = true;
    document.body.classList.remove("lock");
    currentIndex = -1;
    history.replaceState(null, "", window.location.pathname + window.location.search);
    if (lastTile) lastTile.focus();
  }

  function step(delta) {
    if (!filtered.length) return;
    currentIndex = (currentIndex + delta + filtered.length) % filtered.length;
    updateLightbox();
  }

  gallery.addEventListener("click", (event) => {
    const tile = event.target.closest(".tile");
    if (!tile) return;
    lastTile = tile;
    const index = filtered.findIndex((p) => p.id === tile.dataset.id);
    if (index >= 0) openLightbox(index);
  });

  albumsNav.addEventListener("click", (event) => {
    const button = event.target.closest(".album-pill");
    if (!button) return;
    applyAlbum(button.dataset.album);
  });

  lbClose.addEventListener("click", closeLightbox);
  lbPrev.addEventListener("click", () => step(-1));
  lbNext.addEventListener("click", () => step(1));

  document.addEventListener("keydown", (event) => {
    if (lightbox.hidden) return;
    if (event.key === "Escape") {
      closeLightbox();
    } else if (event.key === "ArrowLeft") {
      step(-1);
    } else if (event.key === "ArrowRight") {
      step(1);
    }
  });

  async function init() {
    const response = await fetch("photos.json");
    const data = await response.json();
    photos = data.photos || [];
    document.title = data.title || document.title;
    countEl.textContent = String(photos.length);
    buildAlbums();
    applyAlbum("all");

    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          renderBatch();
        }
      },
      { rootMargin: "900px" }
    );
    observer.observe(sentinel);

    const match = window.location.hash.match(/^#p-(.+)$/);
    if (match) {
      const index = filtered.findIndex((p) => p.id === decodeURIComponent(match[1]));
      if (index >= 0) {
        ensureRendered(index);
        requestAnimationFrame(() => openLightbox(index));
      }
    }
  }

  init().catch((error) => {
    console.error(error);
    countEl.textContent = "0";
  });
})();
