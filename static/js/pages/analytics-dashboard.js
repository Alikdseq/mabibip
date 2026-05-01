function readJsonScript(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent || 'null');
  } catch {
    return null;
  }
}

(() => {
  const labels = readJsonScript('analytics-labels') || [];
  const regClients = readJsonScript('analytics-reg-clients') || [];
  const regOwners = readJsonScript('analytics-reg-owners') || [];
  const regStations = readJsonScript('analytics-reg-stations') || [];
  const bookCr = readJsonScript('analytics-book-created') || [];
  const bookDone = readJsonScript('analytics-book-completed') || [];
  const pieVals = readJsonScript('analytics-review-pie') || [];
  const points = readJsonScript('analytics-map-points') || [];

  if (window.Chart) {
    const commonOpts = { responsive: true, maintainAspectRatio: false };

    new window.Chart(document.getElementById('chartRegs'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Клиенты', data: regClients, borderWidth: 2, tension: 0.25 },
          { label: 'Владельцы СТО', data: regOwners, borderWidth: 2, tension: 0.25 },
          { label: 'Новые СТО', data: regStations, borderWidth: 2, tension: 0.25 },
        ],
      },
      options: {
        ...commonOpts,
        plugins: { legend: { position: 'bottom' } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });

    new window.Chart(document.getElementById('chartBookings'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Создано', data: bookCr },
          { label: 'Завершено (по истории)', data: bookDone },
        ],
      },
      options: {
        ...commonOpts,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          x: { stacked: false },
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });

    new window.Chart(document.getElementById('chartPie'), {
      type: 'doughnut',
      data: {
        labels: ['С отзывом', 'Без отзыва'],
        datasets: [{ data: pieVals, borderWidth: 1 }],
      },
      options: {
        ...commonOpts,
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }

  if (window.ymaps && points.length) {
    window.ymaps.ready(() => {
      const center = [points[0].lat, points[0].lon];
      const map = new window.ymaps.Map('mapYandex', {
        center,
        zoom: points.length === 1 ? 12 : 9,
        controls: ['zoomControl'],
      });
      points.forEach((p) => {
        map.geoObjects.add(new window.ymaps.Placemark([p.lat, p.lon], { balloonContent: p.name }));
      });
    });
  }
})();

