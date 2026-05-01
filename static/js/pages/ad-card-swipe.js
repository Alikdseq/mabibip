/**
 * Мобильные карточки объявлений: индикаторы-точки для горизонтального свайпа по фото.
 * Прокрутка нативная (overflow + scroll-snap).
 */
export function initAdCardSliders(root = document) {
  root.querySelectorAll("[data-pm-ad-slider]").forEach((rootEl) => {
    const track = rootEl.querySelector(".pm-ad-card-slider-track");
    const dotsHost = rootEl.querySelector(".pm-ad-card-slider-dots");
    if (!track) return;
    const slides = track.querySelectorAll(".pm-ad-card-slider-slide");
    if (slides.length < 2) {
      if (dotsHost) dotsHost.remove();
      return;
    }

    const dots = [];
    if (dotsHost) {
      dotsHost.innerHTML = "";
      slides.forEach((_, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "pm-ad-card-slider-dot" + (i === 0 ? " is-active" : "");
        b.setAttribute("aria-label", "Фото " + (i + 1));
        b.addEventListener("click", () => {
          const w = track.clientWidth;
          track.scrollTo({ left: w * i, behavior: "smooth" });
        });
        dotsHost.appendChild(b);
        dots.push(b);
      });
    }

    let scrollTick = null;
    const syncDots = () => {
      if (!dots.length) return;
      const w = track.clientWidth || 1;
      const i = Math.round(track.scrollLeft / w);
      const clamped = Math.max(0, Math.min(i, dots.length - 1));
      dots.forEach((d, j) => d.classList.toggle("is-active", j === clamped));
    };

    track.addEventListener(
      "scroll",
      () => {
        if (scrollTick) cancelAnimationFrame(scrollTick);
        scrollTick = requestAnimationFrame(syncDots);
      },
      { passive: true },
    );

    window.addEventListener("resize", syncDots, { passive: true });
    syncDots();
  });
}
