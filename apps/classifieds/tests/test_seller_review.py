"""Отзывы о продавце в объявлениях."""

import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.classifieds.models import Ad, AdKind, SellerReview, SellerReviewModerationStatus
from apps.users.models import User


@pytest.mark.django_db
def test_seller_review_unique_per_author_seller():
    """H1: уникальность пары (author, seller) на уровне БД."""
    buyer = User.objects.create_user(phone="+79992001001", password="x")
    seller = User.objects.create_user(phone="+79992001002", password="x")
    SellerReview.objects.create(author=buyer, seller=seller, rating=5, text="ok")
    with pytest.raises(IntegrityError):
        SellerReview.objects.create(author=buyer, seller=seller, rating=4, text="dup")


@pytest.mark.django_db
def test_seller_review_create_redirects_if_duplicate(client):
    buyer = User.objects.create_user(phone="+79992001003", password="x")
    seller = User.objects.create_user(phone="+79992001004", password="x")
    client.force_login(buyer)
    SellerReview.objects.create(author=buyer, seller=seller, rating=5, text="first")
    url = reverse("classifieds:seller_review_create", kwargs={"public_id": seller.public_id})
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_seller_profile_shows_ok_reviews_only(client):
    buyer = User.objects.create_user(phone="+79992001005", password="x")
    seller = User.objects.create_user(phone="+79992001006", password="x")
    SellerReview.objects.create(
        author=buyer,
        seller=seller,
        rating=5,
        text="visible",
        moderation_status=SellerReviewModerationStatus.OK,
    )
    SellerReview.objects.create(
        author=User.objects.create_user(phone="+79992001007", password="x"),
        seller=seller,
        rating=1,
        text="hidden",
        moderation_status=SellerReviewModerationStatus.HIDDEN,
    )
    url = reverse("classifieds:seller_profile", kwargs={"public_id": seller.public_id})
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.context["seller_reviews"]) == 1
    assert response.context["seller_reviews"][0].text == "visible"


@pytest.mark.django_db
def test_ad_card_lists_review_link_for_buyer_not_owner(client):
    buyer = User.objects.create_user(phone="+79992001010", password="x")
    seller = User.objects.create_user(phone="+79992001011", password="x")
    Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Запчасть",
        price=100,
        is_published=True,
    )
    client.force_login(buyer)
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    review_url = reverse("classifieds:seller_review_create", kwargs={"public_id": seller.public_id})
    assert review_url in r.content.decode()


@pytest.mark.django_db
def test_ad_card_lists_no_review_link_for_owner(client):
    seller = User.objects.create_user(phone="+79992001012", password="x")
    Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Своё",
        price=100,
        is_published=True,
    )
    client.force_login(seller)
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    review_url = reverse("classifieds:seller_review_create", kwargs={"public_id": seller.public_id})
    assert review_url not in r.content.decode()


@pytest.mark.django_db
def test_ad_card_lists_no_review_link_after_review(client):
    buyer = User.objects.create_user(phone="+79992001013", password="x")
    seller = User.objects.create_user(phone="+79992001014", password="x")
    Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Запчасть",
        price=100,
        is_published=True,
    )
    SellerReview.objects.create(author=buyer, seller=seller, rating=5, text="ok")
    client.force_login(buyer)
    r = client.get(reverse("classifieds:ads_list"))
    assert r.status_code == 200
    review_url = reverse("classifieds:seller_review_create", kwargs={"public_id": seller.public_id})
    assert review_url not in r.content.decode()
