"""
موقتِ اعتبارسنجی (نه بخشی از تست‌های پروژه):
  - ذخیرهٔ محلی تصویر + سرو شدن روی /static
  - formatter تولِ‌نقش‌نگاری
  - __str__ مدل‌ها برای نمایش خوانا در SQLAdmin
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

# کنسول ویندوز به‌صورت پیش‌فرض cp1252 است و متن فارسی را چاپ نمی‌کند.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("JWT_SECRET_KEY", "validation-secret")

from app.admin.views import (  # noqa: E402
    ARTIST_UPLOAD_FOLDER,
    SONG_UPLOAD_FOLDER,
    _image_column_formatter,
)
from app.models import Artist, Song  # noqa: E402
from app.services.storage import (  # noqa: E402
    delete_local_file,
    resolve_media_backend,
    save_local_file,
    store_media_image,
)

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05570c1f8b0000000049454e44ae426082"
)


def main() -> None:
    backend = resolve_media_backend()
    print(f"[1] media backend = {backend}")
    assert backend in {"local", "s3"}

    result = save_local_file(
        PNG_BYTES, "عکس من.png", folder=ARTIST_UPLOAD_FOLDER, content_type="image/png"
    )
    print(f"[2] saved -> url={result.url} key={result.key}")
    assert result.url.startswith("/static/uploads/artists/")
    assert result.url.endswith(".png"), "MIME → .png extension inference failed"
    assert " " not in result.key and not any(
        ord(ch) > 127 for ch in result.key
    ), "filename must be a safe UUID (no spaces / non-ASCII)"

    on_disk = Path("static") / result.key
    assert on_disk.is_file(), f"file missing on disk: {on_disk}"
    print(f"[3] exists on disk: {on_disk} ({on_disk.stat().st_size} bytes)")

    assert delete_local_file(result.url) is True
    assert not on_disk.exists()
    print("[4] delete_local_file(url) removed the file")

    assert delete_local_file("static/../app/main.py") is False
    assert delete_local_file("/static/uploads/") is False
    print("[5] path-traversal / directory deletion rejected")

    # در محیط محلی، مسیر رسانه هم باید محلی باشد.
    if backend == "local":
        media = store_media_image(PNG_BYTES, "x.png", "image/png")
        assert media.url.startswith("/static/"), media.url
        assert delete_local_file(media.url) is True
        print(f"[6] store_media_image -> {media.url} (local, cleaned up)")

    artist = Artist(id=7, name="سید مجید بنی‌فاطمه")
    song = Song(id=3, title="امشب شب قدره")
    song.artist = artist
    assert str(artist) == "سید مجید بنی‌فاطمه", str(artist)
    assert str(song) == "امشب شب قدره — سید مجید بنی‌فاطمه", str(song)
    print(f"[7] readable names: artist={str(artist)!r} song={str(song)!r}")

    formatter = _image_column_formatter("cover_url")
    empty = formatter(Artist(id=1, name="x"), "cover_url", None)
    assert "—" in str(empty)
    rich = formatter(Artist(id=1, name="x", cover_url="/static/uploads/a.jpg"), "cover_url", None)
    assert '<img src="/static/uploads/a.jpg"' in str(rich)
    escaped = formatter(
        Artist(id=1, name='"><script>', cover_url='"><script>alert(1)</script>'),
        "cover_url",
        None,
    )
    assert "<script>" not in str(escaped), "formatter must escape values"
    print("[8] image formatter: empty placeholder, thumbnail, XSS-escaped")

    print("\nALL VALIDATION CHECKS PASSED")


if __name__ == "__main__":
    main()