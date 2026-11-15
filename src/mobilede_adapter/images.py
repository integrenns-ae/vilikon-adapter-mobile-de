"""Photos waiting for a listing. Someone hands over a photo as a file (a phone picture, HEIC or PNG included); it is
turned into a JPG that mobile.de takes and kept here under a short id until create_ad or set_images uses it. Nothing
goes to mobile.de before that, so handing over a photo needs no approval.

Every photo is encoded anew: turned upright, without its metadata (a phone writes the location into it), at most
MAX_EDGE pixels on the long side and at most MAX_BYTES large."""

from __future__ import annotations

import hashlib
import io
import re
import time
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

try:  # photos from an iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

MAX_BYTES = 2_097_152  # mobile.de's limit per image
MAX_INPUT = 30 * 1024 * 1024
MAX_EDGE = 1920
KEEP_S = 7 * 86400
QUALITIES = (88, 80, 72, 64)
ID = re.compile(r"^img-[0-9a-f]{16}$")
Image.MAX_IMAGE_PIXELS = 80_000_000  # a bigger "photo" is an attack, not a car


class ImageError(Exception):
    """`key` names the sentence in texts.py."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def to_jpeg(data: bytes) -> tuple[bytes, int, int]:
    """The photo as a JPG mobile.de takes, with its width and height."""
    if len(data) > MAX_INPUT:
        raise ImageError("image_input_too_big")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise ImageError("image_unreadable") from None
    img = img.convert("RGB")
    edge = MAX_EDGE
    while edge >= 640:
        img.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        for quality in QUALITIES:
            out = io.BytesIO()
            img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
            if out.tell() <= MAX_BYTES:
                return out.getvalue(), img.width, img.height
        edge = int(edge * 0.75)
    raise ImageError("image_too_big")


class ImageStore:
    def __init__(self, data_dir: Path) -> None:
        self.dir = Path(data_dir) / "images"

    def add(self, data: bytes) -> dict:
        jpg, width, height = to_jpeg(data)
        image_id = "img-" + hashlib.sha256(jpg).hexdigest()[:16]
        self.dir.mkdir(parents=True, exist_ok=True)
        self._prune()
        (self.dir / f"{image_id}.jpg").write_bytes(jpg)
        return {"image": image_id, "width": width, "height": height, "bytes": len(jpg)}

    def get(self, image_id: str) -> bytes:
        image_id = str(image_id).strip()
        if not ID.match(image_id):
            raise ImageError("image_unknown")
        try:
            return (self.dir / f"{image_id}.jpg").read_bytes()
        except OSError:
            raise ImageError("image_unknown") from None

    def _prune(self) -> None:
        """Photos nobody used within a week are dropped."""
        old = time.time() - KEEP_S
        for f in self.dir.glob("img-*.jpg"):
            try:
                if f.stat().st_mtime < old:
                    f.unlink()
            except OSError:
                pass
