"""사진 업로드 관문 — **저장 전에 통과해야 하는 것** (D-43 · D-36).

D-43 이 관문 5단계를 정했고 3차는 사진을 안 붙였다 —
`app/routes/pets.py` 가 *"붙일 때 **관문 5단계를 통과한 것만** 저장한다"* 로 조건을 남겼다.
4차가 Django 로 사진을 붙이면서 그 조건을 지나쳤고(2026-08-26 점검), 이 모듈이 그것을 메운다.

## 왜 프레임워크 밖인가

Django 안에 두면 **CI 가 안 본다** — `testpaths = ["tests"]` 가 앱 폴더를 안 보기 때문이다.
여기 두면 순수 함수라 `tests/test_image_gate.py` 가 그대로 돈다.
그리고 이것은 **배달 계층이 아니라 개인정보 처리**다. D-36 이 사는 곳이 여기다.

## 무엇을 막는가

    ① 크기·형식      상한을 넘거나 아는 형식이 아니면 거절
    ② 진짜 이미지인가  Pillow 가 못 열면 이미지가 아니다 (확장자는 거짓말한다)
    ③ 재인코딩       ← **EXIF 가 여기서 사라진다.** GPS 좌표가 실려 있다
    ④ 크기 축소       디스크와 대역폭

🔴 **③이 이 모듈의 존재 이유다.** 스마트폰 사진에는 촬영 위치가 들어 있고,
그대로 저장하면 **보호자의 집 위치가 서버에 남는다.** D-01 이 이 도메인을 고른 이유 중
하나가 *"개인정보 리스크가 낮다"* 였는데, 사진이 그 전제를 깬다.

⚠️ **회전 정보만은 버리기 전에 픽셀에 반영한다.** EXIF 를 통째로 지우면 세로로 찍은 사진이
가로로 눕는다 — 개인정보를 지우려다 사진을 망가뜨리는 것이라, `exif_transpose` 를 먼저 건다.

## 얼굴 검출은 하지 않는다

D-43 원안의 5단계 중 얼굴 검출은 모델을 하나 더 들여야 한다. 위 넷만으로 **위치·신원이
새는 경로는 닫힌다.** 필요해지면 이 함수 앞에 한 단계를 더 놓는다 —
지금 안 하는 것을 안 한다고 적어 두는 편이, 한다고 적고 안 하는 것보다 낫다 (D-58).
"""

from __future__ import annotations

import io
import uuid

#: 원본 상한. 이걸 넘으면 열어 보지도 않는다 — 압축 폭탄을 메모리에 올리지 않기 위해서다.
MAX_BYTES = 5 * 1024 * 1024

#: 긴 변 상한. 프로필 카드와 목록에 쓰는 크기다.
MAX_SIDE = 1280

#: 받아 주는 형식. **확장자가 아니라 Pillow 가 판정한 형식**이다.
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

#: 내보내는 형식. 하나로 모아 두면 뒤쪽(서빙·썸네일)이 단순해진다.
OUT_FORMAT = "JPEG"
OUT_EXT = ".jpg"
OUT_QUALITY = 85


class ImageRejected(ValueError):
    """관문을 통과하지 못했다. **메시지는 사용자에게 그대로 보여도 되게 쓴다.**"""


def sanitize(data: bytes, *, max_bytes: int = MAX_BYTES, max_side: int = MAX_SIDE) -> bytes:
    """관문을 통과한 **새 이미지 바이트**를 낸다. 실패하면 `ImageRejected`.

    원본 바이트는 **버린다.** 통과한 것을 저장하는 게 아니라 **새로 만든 것**을 저장한다 —
    그래야 원본에 실린 것이 따라오지 않는다.
    """
    if not data:
        raise ImageRejected("빈 파일입니다.")
    if len(data) > max_bytes:
        mb = max_bytes / 1024 / 1024
        raise ImageRejected(f"파일이 너무 큽니다. {mb:.0f}MB 이하로 올려 주세요.")

    try:
        from PIL import Image, ImageOps
    except ImportError as e:  # pragma: no cover - 의존성 누락은 설치 문제다
        raise RuntimeError("Pillow 가 없습니다 — pip install -e '.[...]' -c constraints.txt") from e

    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()  # 손상 여부. verify() 뒤에는 그 객체를 못 쓴다
    except Exception as e:
        raise ImageRejected("이미지 파일이 아니거나 손상됐습니다.") from e

    if fmt not in ALLOWED_FORMATS:
        allowed = " · ".join(sorted(ALLOWED_FORMATS))
        raise ImageRejected(f"{fmt or '알 수 없는'} 형식은 받지 않습니다. ({allowed})")

    # verify() 가 파일 포인터를 소모하므로 다시 연다.
    img = Image.open(io.BytesIO(data))
    # 🔴 회전 정보를 **픽셀로 옮긴 뒤에** EXIF 를 버린다. 순서를 바꾸면 사진이 눕는다.
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")  # 알파·팔레트를 정리한다. JPEG 는 알파를 모른다
    img.thumbnail((max_side, max_side))

    out = io.BytesIO()
    # `save` 에 exif 를 넘기지 않는다 = 메타데이터가 따라오지 않는다.
    img.save(out, format=OUT_FORMAT, quality=OUT_QUALITY, optimize=True)
    return out.getvalue()


def new_filename() -> str:
    """저장할 이름. **원본 파일명을 쓰지 않는다** — 이름에 사람 이름·날짜가 들어간다."""
    return f"{uuid.uuid4().hex}{OUT_EXT}"
