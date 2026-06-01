import { registerServiceCategoryTilesAlpine } from '../app/service-category-tiles.js';

(() => {
  const suggestUrlEl = document.getElementById('home-suggest-url');
  const nearbyUrlEl = document.getElementById('home-nearby-url');
  const suggestUrl = suggestUrlEl ? JSON.parse(suggestUrlEl.textContent || '""') : '';
  const nearbyMapUrl = nearbyUrlEl ? JSON.parse(nearbyUrlEl.textContent || '""') : '';

  registerServiceCategoryTilesAlpine();

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('homeSearch', () => ({
      q: '',
      results: [],
      ambiguous: '',
      open: false,
      loading: false,
      blurTimer: null,
      debounce: null,
      suggestUrl,
      get panelVisible() {
        if (!this.open) return false;
        if (this.loading || this.results.length > 0 || this.ambiguous) return true;
        return this.q.trim().length >= 1;
      },
      onFocusSearch() {
        clearTimeout(this.blurTimer);
        this.open = true;
        this.fetchSuggestions();
      },
      onBlurSearch() {
        clearTimeout(this.blurTimer);
        this.blurTimer = setTimeout(() => {
          this.open = false;
        }, 220);
      },
      fetchSuggestions() {
        if (this.q.trim().length < 2) {
          this.results = [];
          this.ambiguous = '';
          this.loading = false;
          this.open = false;
          return;
        }
        this.open = true;
        clearTimeout(this.debounce);
        this.debounce = setTimeout(async () => {
          this.loading = true;
          this.results = [];
          try {
            const r = await fetch(
              this.suggestUrl +
                '?q=' +
                encodeURIComponent(this.q.trim()) +
                '&limit_services=8&limit_sections=6&limit_masters=4&limit_stations=4'
            );
            if (!r.ok) {
              throw new Error(String(r.status));
            }
            const data = await r.json();
            this.results = (data.results || []).slice(0, 20);
            this.ambiguous = data.ambiguous_hint || '';
          } catch {
            this.results = [];
            this.ambiguous = '';
          } finally {
            this.loading = false;
          }
        }, 320);
      },
      pick(url) {
        window.location.href = url;
      },
    }));

    window.Alpine.data('nearbyBlock', () => ({
      loading: false,
      error: null,
      nearbyMapUrl,
      locate() {
        if (!navigator.geolocation) {
          this.error = 'Геолокация не поддерживается браузером';
          return;
        }
        this.loading = true;
        this.error = null;
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            const u = new URL(this.nearbyMapUrl, window.location.origin);
            u.searchParams.set('lat', lat);
            u.searchParams.set('lng', lng);
            u.searchParams.set('radius_km', '10');
            window.location.href = u.pathname + u.search;
          },
          () => {
            this.loading = false;
            this.error = 'Доступ к геолокации отклонён. Разрешите доступ или откройте сайт по HTTPS / localhost.';
          },
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
      },
    }));
  });
})();

