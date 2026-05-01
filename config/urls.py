"""
URL configuration for МаБибип MVP.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from apps.core.sitemaps import (
    AutoShopSitemap,
    CarBrandSitemap,
    ClassifiedAdsSitemap,
    ServiceCategorySitemap,
    ServiceSectionSitemap,
    StationSitemap,
    StaticViewSitemap,
)
from apps.core.map_api import MapPlacesAPIView
from apps.stations.api import SearchSuggestAPIView, StationsNearbyAPIView
from apps.chat import unified_chat_views
from apps.core import views as core_views
from apps.stations.views import HomePageView

SEO_SITEMAPS = {
    "static": StaticViewSitemap,
    "services": ServiceCategorySitemap,
    "sections": ServiceSectionSitemap,
    "brands": CarBrandSitemap,
    "stations": StationSitemap,
    "ads": ClassifiedAdsSitemap,
    "shops": AutoShopSitemap,
}

urlpatterns = [
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": SEO_SITEMAPS},
        name="seo_sitemap",
    ),
    path("visitor-city/", core_views.set_visitor_city, name="set_visitor_city"),
    path("", HomePageView.as_view(), name="home"),
    path("", include("apps.stations.landing_urls")),
    path("legal/", include("apps.legal.urls")),
    path("cabinet/", include("apps.users.cabinet_urls")),
    path("sto/cabinet/", include("apps.stations.owner_urls")),
    path("shops/cabinet/", include("apps.classifieds.shop_owner_urls")),
    path("sto/", include("apps.stations.urls")),
    path("accounts/", include("apps.users.urls")),
    path("oauth/", include("allauth.urls")),
    path("billing/", include("apps.billing.urls")),
    path("secure-erp/", include("apps.erp.urls")),
    path("secure-admin/", admin.site.urls),
    path("api/stations/nearby/", StationsNearbyAPIView.as_view(), name="api_stations_nearby"),
    path("api/search/suggest/", SearchSuggestAPIView.as_view(), name="api_search_suggest"),
    path("api/map/places/", MapPlacesAPIView.as_view(), name="api_map_places"),
    path("api/", include("apps.chat.api_urls")),
    path("api/calls/", include("apps.calls.api_urls")),
    path("api/", include("apps.classifieds.api_urls")),
    path("chat/direct/<int:thread_id>/send/", unified_chat_views.direct_thread_send, name="chat_direct_send"),
    path("", include("apps.classifieds.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "SERVE_MEDIA", False):
    # Раздача media в docker-compose (локально). В проде медиа должен отдавать reverse-proxy / CDN.
    _prefix = (settings.MEDIA_URL or "/media/").lstrip("/")
    urlpatterns += [
        re_path(rf"^{_prefix}(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler404 = "config.views.handler404"
handler500 = "config.views.handler500"
