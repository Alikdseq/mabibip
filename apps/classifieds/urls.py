from django.urls import path

from . import views

app_name = "classifieds"

urlpatterns = [
    path("ads/", views.AdsListView.as_view(), name="ads_list"),
    path("ads/<int:pk>/", views.AdDetailView.as_view(), name="ad_detail"),
    path("ads/<int:pk>/call-click/", views.ad_call_click_log, name="ad_call_click"),
    path("ads/<int:pk>/favorite/", views.favorite_ad_toggle, name="favorite_ad_toggle"),
    path("ads/<int:pk>/chat/", views.ad_start_chat, name="ad_start_chat"),
    path("ads/<int:pk>/safe-buy/", views.ad_safe_buy_start, name="ad_safe_buy_start"),
    path("seller/<uuid:public_id>/", views.SellerProfileView.as_view(), name="seller_profile"),
    path(
        "seller/<uuid:public_id>/review/",
        views.seller_review_create,
        name="seller_review_create",
    ),
    path("shops/", views.ShopListView.as_view(), name="shops_list"),
    path("shops/<slug:slug>/", views.ShopDetailView.as_view(), name="shop_detail"),
    # cabinet (client)
    path("cabinet/ads/", views.MyAdsListView.as_view(), name="my_ads"),
    path("cabinet/ads/new/", views.MyAdCreateView.as_view(), name="my_ad_create"),
    path("cabinet/ads/<int:pk>/edit/", views.MyAdUpdateView.as_view(), name="my_ad_edit"),
    path("cabinet/ads/<int:pk>/unpublish/", views.MyAdUnpublishView.as_view(), name="my_ad_unpublish"),
    path("cabinet/ad-photos/<int:pk>/delete/", views.ad_photo_delete, name="ad_photo_delete"),
    path("cabinet/deals/", views.MyDealsListView.as_view(), name="my_deals"),
    path("cabinet/deals/<int:pk>/", views.DealDetailView.as_view(), name="deal_detail"),
    path("cabinet/deals/<int:deal_id>/cancel/", views.classifieds_deal_cancel, name="deal_cancel"),
    path("cabinet/deals/<int:deal_id>/shipped/", views.classifieds_deal_mark_shipped, name="deal_mark_shipped"),
    path("cabinet/deals/<int:deal_id>/received/", views.classifieds_deal_confirm_received, name="deal_confirm_received"),
    # business cabinet (autoshop)
    path("sto/cabinet/products/", views.biz_products, name="biz_products"),
]

