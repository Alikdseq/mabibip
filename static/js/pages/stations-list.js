import { serviceCategoryTilesFactory } from '../app/service-category-tiles.js';

(() => {
  // Alpine expects this factory to exist in global scope.
  window.catalogQuickFilters = function catalogQuickFilters({
    entry,
    quick,
    hasBrand,
    hasService,
    hasSection,
    serviceTileCount,
  }) {
    const showNone = (quick || '') === '1';
    const showByEntry = (entry || '').toLowerCase();
    const svcSelected = Boolean(hasService || hasSection);
    const showBrandsInitial = !showNone && (showByEntry === 'service' || (!showByEntry && !hasBrand));
    const showServicesInitial = !showNone && (showByEntry === 'brand' || (!showByEntry && !svcSelected));
    const stc = Number(serviceTileCount) || 0;

    return {
      ...serviceCategoryTilesFactory(stc),
      brandsMore: false,
      showBrands: showBrandsInitial,
      showServices: showServicesInitial,
      serviceTileCount: stc,
      get controlsVisible() {
        return !this.showBrands && !this.showServices;
      },
      toggleMoreBrands() {
        this.brandsMore = !this.brandsMore;
      },
      toggleBrands() {
        this.showBrands = !this.showBrands;
        this.showServices = false;
        this.brandsMore = false;
      },
      toggleServices() {
        this.showServices = !this.showServices;
        this.showBrands = false;
        this.brandsMore = false;
      },
      _getHidden(name) {
        const el = document.querySelector(`form[id^="catalog-filters-"] input[name="${name}"]`);
        return (el?.value || '').toString();
      },
      _setHidden(name, value) {
        document.querySelectorAll(`form[id^="catalog-filters-"] input[name="${name}"]`).forEach((el) => {
          el.value = value ?? '';
        });
      },
      _setSearch(value) {
        document.querySelectorAll(`form[id^="catalog-filters-"] input[name="q"]`).forEach((el) => {
          el.value = value ?? '';
        });
      },
      _clearCats() {
        document.querySelectorAll(`form[id^="catalog-filters-"] input[name="cat"]`).forEach((el) => {
          el.checked = false;
        });
      },
      _checkCat(catId) {
        if (!catId) return;
        document.querySelectorAll(`form[id^="catalog-filters-"] input[name="cat"][value="${catId}"]`).forEach((el) => {
          el.checked = true;
        });
      },
      _submit() {
        this._setHidden('quick', '1');
        if (window.htmx) {
          window.htmx.trigger('#catalog-filters-desk', 'submit');
        } else {
          const f = document.getElementById('catalog-filters-desk');
          if (f) f.submit();
        }
        this.brandsMore = false;
      },
      applyBrand(brandSlug) {
        this._setHidden('brand', brandSlug);
        this._setHidden('entry', 'brand');
        // После выбора марки остаётся выбор раздела, если он ещё не выбран.
        const sec = this._getHidden('section');
        this.showBrands = false;
        this.showServices = !sec;
        this._submit();
      },
      clearBrand() {
        this._setHidden('brand', '');
        this._setHidden('entry', '');
        this.showServices = false;
        this.showBrands = true;
        this._submit();
      },
      applyService(payload) {
        const kind = (payload?.kind || '').toLowerCase();
        const catId = (payload?.catId || '').toString();
        const sectionSlug = (payload?.sectionSlug || '').toString();
        const qVal = (payload?.q || '').toString();
        if (kind === 'section' && sectionSlug) {
          this._clearCats();
          this._setSearch('');
          this._setHidden('section', sectionSlug);
          this._setHidden('entry', 'service');
          // После выбора раздела остаётся выбор марки, если она ещё не выбрана.
          const brand = this._getHidden('brand');
          this.showServices = false;
          this.showBrands = !brand;
          this._submit();
          return;
        }
        if (kind === 'category' && catId) {
          this._clearCats();
          this._checkCat(catId);
          this._setSearch('');
        } else {
          this._clearCats();
          this._setSearch(qVal);
        }
        this._setHidden('section', '');
        this._setHidden('entry', 'service');
        const brand = this._getHidden('brand');
        this.showServices = false;
        this.showBrands = !brand;
        this._submit();
      },
    };
  };

  // Geo-locate buttons for filter forms
  document.querySelectorAll('.js-geo-locate').forEach((btn) => {
    btn.addEventListener('click', () => {
      const s = btn.getAttribute('data-suffix');
      if (!navigator.geolocation) {
        alert('Геолокация не поддерживается браузером');
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const latEl = document.getElementById('user-lat-' + s);
          const lngEl = document.getElementById('user-lng-' + s);
          if (latEl) latEl.value = pos.coords.latitude;
          if (lngEl) lngEl.value = pos.coords.longitude;
        },
        () => alert('Не удалось получить координаты'),
        { enableHighAccuracy: false, timeout: 12000, maximumAge: 60000 }
      );
    });
  });
})();

