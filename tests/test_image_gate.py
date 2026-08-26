"""사진 업로드 관문 (D-43 · D-36) — `pettriage.privacy.images`.

**이 파일이 `tests/` 에 있는 것이 요점이다.** 관문을 Django 앱 안에 두었으면
`testpaths = ["tests"]` 가 안 봐서 CI 가 한 줄도 실행하지 않았을 것이다 (13 §5).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pettriage.privacy.images import (
    ImageRejected,
    new_filename,
    sanitize,
)

# 🔴 `importorskip` 을 쓰지 않는다. Pillow 는 **핵심 의존성**이라 없으면 설치가 잘못된
#    것이고, 그때는 조용히 건너뛸 게 아니라 **시끄럽게 죽어야 한다.**
#    D-48 교훈 #6 — `importorskip` 이 25건을 모듈째 숨겨 회원가입이 안 되는 것을 덮었다.


def _jpeg(size=(40, 20), exif=None, fmt="JPEG") -> bytes:
    im = Image.new("RGB", size, "red")
    buf = io.BytesIO()
    if exif is not None:
        im.save(buf, fmt, exif=exif)
    else:
        im.save(buf, fmt)
    return buf.getvalue()


# ── ③ 재인코딩 — 이 모듈의 존재 이유 ─────────────────────────


def test_exif가_사라진다():
    """🔴 **핵심.** 스마트폰 사진의 촬영 위치가 그대로 저장되면 안 된다."""
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"  # Make
    exif[0x0110] = "TestModel"  # Model
    src = _jpeg(exif=exif)
    assert Image.open(io.BytesIO(src)).getexif(), "준비 실패 — 원본에 EXIF 가 있어야 한다"

    out = Image.open(io.BytesIO(sanitize(src)))
    assert not dict(out.getexif()), "EXIF 가 남았다 — 위치·기기 정보가 새는 경로다"


def test_회전정보는_픽셀로_옮긴다():
    """EXIF 를 버리기 전에 방향을 반영한다. 안 하면 세로 사진이 눕는다."""
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation — 시계방향 90도로 봐야 한다
    src = _jpeg(size=(40, 20), exif=exif)

    out = Image.open(io.BytesIO(sanitize(src)))
    assert out.size == (20, 40), f"방향이 반영되지 않았다: {out.size}"


def test_원본_바이트를_쓰지_않는다():
    src = _jpeg()
    assert sanitize(src) != src, "원본을 그대로 돌려주면 관문이 아니다"


# ── ① 크기·형식 ────────────────────────────────────────────


def test_너무_큰_파일은_거절한다():
    with pytest.raises(ImageRejected, match="너무 큽니다"):
        sanitize(b"x" * 200, max_bytes=100)


def test_빈_파일은_거절한다():
    with pytest.raises(ImageRejected):
        sanitize(b"")


def test_이미지가_아니면_거절한다():
    """확장자는 거짓말한다 — **내용으로 판정한다.**"""
    with pytest.raises(ImageRejected, match="이미지 파일이 아니"):
        sanitize(b"GIF89a not really an image")


def test_받지_않는_형식은_거절한다():
    buf = io.BytesIO()
    Image.new("P", (10, 10)).save(buf, "GIF")
    with pytest.raises(ImageRejected, match="형식은 받지 않습니다"):
        sanitize(buf.getvalue())


# ── ④ 축소 ────────────────────────────────────────────────


def test_긴_변을_상한까지_줄인다():
    out = Image.open(io.BytesIO(sanitize(_jpeg(size=(300, 150)), max_side=100)))
    assert max(out.size) == 100
    assert out.size == (100, 50), "가로세로 비를 지켜야 한다"


def test_작은_사진은_늘리지_않는다():
    out = Image.open(io.BytesIO(sanitize(_jpeg(size=(30, 20)), max_side=100)))
    assert out.size == (30, 20)


def test_알파가_있어도_통과한다():
    """PNG 투명 배경. JPEG 는 알파를 모르므로 RGB 로 정리해야 한다."""
    buf = io.BytesIO()
    Image.new("RGBA", (20, 20), (255, 0, 0, 128)).save(buf, "PNG")
    out = Image.open(io.BytesIO(sanitize(buf.getvalue())))
    assert out.mode == "RGB"


# ── ② 파일명 ──────────────────────────────────────────────


def test_파일명은_원본과_무관하다():
    a, b = new_filename(), new_filename()
    assert a != b
    assert a.endswith(".jpg")
    assert len(a) == 32 + 4, "uuid4 hex + 확장자"
