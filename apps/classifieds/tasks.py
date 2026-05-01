from __future__ import annotations

import io

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from PIL import Image

from .models import AdPhoto, ImageHash


def _ahash_hex(img: Image.Image) -> str:
    """
    Lightweight perceptual hash (aHash).
    Returns 16-hex string (64 bits) as a stable key.
    """
    im = img.convert("L").resize((8, 8))
    px = list(im.getdata())
    avg = sum(px) / 64.0
    bits = 0
    for i, v in enumerate(px):
        if v >= avg:
            bits |= 1 << i
    return f"{bits:016x}"


@shared_task(name="apps.classifieds.tasks.compute_ad_photo_hash")
def compute_ad_photo_hash(photo_id: int) -> None:
    photo = (
        AdPhoto.objects.select_related("ad", "ad__owner")
        .only("id", "image", "ad_id", "ad__owner_id")
        .filter(pk=int(photo_id))
        .first()
    )
    if not photo or not getattr(photo, "image", None):
        return

    try:
        # storage backend-safe: open via File
        with photo.image.open("rb") as f:
            data = f.read()
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return

    phash = _ahash_hex(img)

    with transaction.atomic():
        ImageHash.objects.update_or_create(photo=photo, defaults={"phash": phash})

    # Very first stage: exact-hash duplicates across different owners → mark suspicious.
    owner_id = getattr(photo.ad, "owner_id", None)
    if not owner_id:
        return

    dup_exists = (
        ImageHash.objects.filter(phash=phash)
        .exclude(photo_id=photo.pk)
        .exclude(photo__ad__owner_id=owner_id)
        .exists()
    )
    if dup_exists:
        User = get_user_model()
        User.objects.filter(pk=owner_id, is_suspicious=False).update(is_suspicious=True)

