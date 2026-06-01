/**
 * Плитки категорий услуг: 2 ряда (4 на телефоне, 8 на sm+), «Ещё» — все остальные.
 */
export function serviceCategoryTilesFactory(total) {
  const t = Number(total) || 0;
  return {
    total: t,
    expanded: false,
    cols() {
      if (typeof window !== 'undefined' && window.matchMedia('(min-width: 576px)').matches) {
        return 4;
      }
      return 2;
    },
    initialShown() {
      return Math.min(this.cols() * 2, this.total);
    },
    shownCount() {
      if (this.expanded) {
        return this.total;
      }
      return this.initialShown();
    },
    showAt(i) {
      return i < this.shownCount();
    },
    loadMore() {
      this.expanded = true;
    },
    get hasMore() {
      return !this.expanded && this.shownCount() < this.total;
    },
  };
}

export function registerServiceCategoryTilesAlpine() {
  document.addEventListener('alpine:init', () => {
    if (!window.Alpine) {
      return;
    }
    window.Alpine.data('serviceCategoryTiles', (total) => serviceCategoryTilesFactory(total));
  });
}
