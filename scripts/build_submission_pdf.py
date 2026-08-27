"""필수 산출물 → 제출용 PDF 묶음.

    python scripts/build_submission_pdf.py           # 미리 보기 (무엇을 만들지만 찍는다)
    python scripts/build_submission_pdf.py --write   # 제출_4차/ 에 기록

🔴 **PDF 는 생성물이다. 손으로 고치지 않는다.** 원본은 `docs/10`~`docs/14` 다.
   `build_requirements_xlsx.py` · `build_testplan_xlsx.py` 와 같은 규약이다.

## 필요한 것

    pandoc · xelatex · Noto Sans CJK KR · @mermaid-js/mermaid-cli

🪟 **Windows 에는 없다.** 이 스크립트는 Linux(CI·컨테이너)에서 돈다.
   팀원은 만들어진 PDF 를 받아 쓰면 되고, 다시 만들 일이 있으면 그쪽에서 돌린다.

## 왜 이모지를 기호로 바꾸나

문서의 상태 표기가 전부 이모지다 (`✅ 🟡 🔴 ⬜`). 그런데 **PDF 엔진이 쓰는 한국어 폰트에
이모지가 없다** — 그냥 두면 상태 칸이 **빈 채로 인쇄된다.** 경고만 나오고 파일은 만들어지므로
아무도 모른 채 제출될 수 있다 (2026-08-27 확인).

컬러 이모지 폰트를 붙이는 길도 있으나 xelatex 에서 불안정하고, **인쇄물에서는 어차피
흑백이다.** 그래서 폰트에 있는 기호로 바꾼다 — `● ◐ ▲ □` 는 *채움 → 절반 → 경고 → 빈칸*
이라 **표에서 이모지가 하던 역할을 그대로 한다.** 뜻은 각 문서 앞의 범례가 설명한다.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "제출_4차"

#: 이모지 → 폰트에 있는 기호. **뜻이 있는 것만** 바꾸고 장식은 지운다.
SYMBOLS: dict[str, str] = {
    "✅": "●",
    "🟡": "◐",
    "🔴": "▲",
    "⬜": "□",
    "⚠️": "※",
    "⚠": "※",
    "🔒": "[안전]",
    "🔄": "[갱신]",
    "🆕": "[신규]",
    "❌": "[기각]",
    "📌": "※",
    "📎": "※",
    "🌐": "[공개]",
    "🔧": "[작업]",
    "🪟": "[Windows]",
    "🐶": "(개)",
    "🐱": "(고양이)",
    "🦜": "(앵무새)",
    "🐾": "",
    "🔥": "",
    "🌱": "",
    "🌅": "",
    "☀️": "",
    "☀": "",
    "🌙": "",
    "🍪": "",
    "📈": "",
    "🗑️": "",
    "🗑": "",
    "💬": "",
    "📖": "",
    "🔍": "",
    "⚙️": "",
    "⚙": "",
    "🔎": "",
    "➤": "",
}

#: 남은 이모지를 잡는다. **조용히 빠지게 두지 않는다** — 이 스크립트가 있는 이유다.
_LEFTOVER = re.compile("[\U0001f000-\U0001faff✀-➿⬀-⯿️]")

LEGEND = """> **표기** — 원본 문서는 이모지로 상태를 나타낸다. 인쇄용 PDF 에서는 폰트에 있는
> 기호로 바꿨다: **●** 완료·검증됨 · **◐** 구현됐으나 검증 안 됨 · **▲** 미구현·주의가 필요함 ·
> **□** 미착수 · **※** 주의. 뜻은 각 문서의 범례와 같다.
"""

#: 표지 겸 대조표. **다섯 번째 산출물(웹 애플리케이션)은 코드라 PDF 가 될 수 없다** —
#: 어디를 보면 되는지 여기서 가리킨다. 이것이 없으면 제출물에 넷만 있는 것처럼 보인다.
#: 모든 표지에 같은 줄이 찍힌다. 문서마다 다르게 쓰면 그 자체가 어긋난다.
AUTHOR = "오한빈(팀장) — 통합·작성 · 내용 기여: 각 문서 「기여 이력」 · 검토: 팀 전원"
IMPRINT = "SKN 4차 단위 프로젝트 · 팀 save the pet · 제품 PetTriage"

COVER = """# 제출 안내 — 필수 산출물 대조표

**SKN 4차 단위 프로젝트** · 팀 `save the pet` · 제품 **PetTriage**
반려동물 건강 상태 판정(트리아지) — RAG 기반 LLM 질의응답

---

## 필수 산출물 다섯 — 어디를 보면 되나

| # | 요구된 것 | 이 묶음에서 | 쪽 |
|---|---|---|---|
| ① | 요구사항 정의서 | `10_요구사항정의서.pdf` | UC 11 · FR 47 · NFR 24 · 추적표 |
| ② | 화면 설계서 | `11_화면설계서.pdf` | 화면 10장 · 트리아지 3상태 |
| ③ | 시스템 구성도 | `12_시스템구성도.pdf` | 포트 · 라우팅 · 저장소 · AWS 배포 |
| ④ | 테스트 계획 및 결과 보고서 | `13_테스트계획.pdf` | 다섯 층 · 자동 666건 · 수동 51건 |
| ⑤ | **LLM 연동 웹 애플리케이션** | **코드다. 아래 참조** | 저장소 |

⑤ 는 문서가 아니라 동작하는 소프트웨어다. `14_전환설계.pdf` 가 **왜 그렇게 만들었는지**를
설계 결정 D-99 ~ D-110 으로 남긴다.

## ⑤ 웹 애플리케이션 — 어디에 무엇이 있나

| 무엇 | 어디 |
|---|---|
| **RAG · 벡터DB · LangChain 연동** | `src/pettriage/graph/` (LangGraph 노드 18개) · `src/pettriage/rag/` |
| **판정 엔진 · 안전 장치** | `src/pettriage/triage/` · `src/pettriage/compute/` |
| **추론 서비스 (FastAPI)** | `src/pettriage/app/` — `/api/ask` · `/api/health` |
| **웹 애플리케이션 (Django)** | `webapp/` · `accounts/` · `pets/` · `diary/` · `chat/` |
| **화면 템플릿** | `chat/templates/` · `templates/` · `diary/templates/` |
| **배포 설정** | `deploy/` (EC2 운영) · `docker/` · `compose.yaml` (로컬) |
| **테스트** | `tests/` 666건 · `eval/` 골든셋 60건 |

**돌려 보려면** — 저장소 `README.md` 의 「바로 실행하기」. Windows 는 `실행.bat`.

## 이 묶음을 만든 방법

PDF 는 **생성물**이다. 원본은 저장소의 `docs/10` ~ `docs/14` 마크다운이고,
`scripts/build_submission_pdf.py` 가 여기 있는 파일을 만든다.

**손으로 고치지 않는다** — 다음 생성 때 없어진다. 내용이 바뀌었으면 원본을 고치고 다시 만든다.
같은 규약으로 요구사항·테스트 표의 `.xlsx` 도 생성물이다
(`make reqs-xlsx` · `make testplan-xlsx`).

## 읽는 분께

이 문서들은 **무엇을 못 했는지도 적는다.** 상태 표기가 셋으로 갈려 있는 것이 그 때문이다 —
`●` 검증됨 · `◐` 구현됐으나 자동 검증이 없음 · `▲` 미구현.

지금 기능 요구사항 47건 중 **◐ 가 32건**이다. 웹 화면 코드가 CI 테스트 밖에 있어서고,
그 사실을 `13_테스트계획.pdf` §5 가 감추지 않고 적어 두었다. 남은 일은 §5.4 의 7b 다.
"""

#: 제출 묶음의 차례. `(파일, 제목, 요구사항 이름)`
ITEMS: list[tuple[str, str, str]] = [
    ("10_요구사항정의서.md", "요구사항 정의서", "요구사항 정의서"),
    ("11_화면설계서.md", "화면 설계서", "화면 설계서"),
    ("12_시스템구성도.md", "시스템 구성도", "시스템 구성도"),
    ("13_테스트계획.md", "테스트 계획 및 결과 보고서", "테스트 계획·결과 보고서"),
    ("14_전환설계.md", "전환 설계 · 설계 결정 기록", "(참고) 설계 근거"),
]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", **kw)


def _chrome() -> str | None:
    for pat in ("/opt/pw-browsers/chromium*/chrome-linux/chrome", "/usr/bin/chromium*"):
        hits = sorted(Path("/").glob(pat.lstrip("/")))
        if hits:
            return str(hits[-1])
    return None


def render_mermaid(md: str, tmp: Path, stem: str) -> tuple[str, int]:
    """```mermaid 블록을 그림으로 바꾼다.

    못 그리면 **코드 블록 그대로 둔다** — 지우지 않는다. 그림이 없는 것과
    그림이 있었는지도 모르는 것은 다르다.
    """
    chrome = _chrome()
    blocks = re.findall(r"```mermaid\n(.*?)```", md, re.S)
    if not blocks or chrome is None:
        return md, 0

    cfg = tmp / "pc.json"
    cfg.write_text(
        '{"args":["--no-sandbox","--disable-dev-shm-usage"],'
        f'"executablePath":"{chrome}"}}',
        encoding="utf-8",
    )
    drawn = 0
    for i, src in enumerate(blocks):
        mmd, pdf = tmp / f"{stem}_{i}.mmd", tmp / f"{stem}_{i}.pdf"
        mmd.write_text(src, encoding="utf-8")
        r = _run(["mmdc", "-i", str(mmd), "-o", str(pdf), "-p", str(cfg), "-b", "white"])
        if r.returncode == 0 and pdf.exists():
            md = md.replace(
                f"```mermaid\n{src}```",
                f"\n![]({pdf})\n",
                1,
            )
            drawn += 1
    return md, drawn


def to_print(md: str) -> tuple[str, list[str]]:
    """이모지를 기호로. 못 바꾼 것은 **알린다.**"""
    for a, b in SYMBOLS.items():
        md = md.replace(a, b)
    left = sorted(set(_LEFTOVER.findall(md)))
    for ch in left:
        md = md.replace(ch, "")
    return md, left


#: 쪽당 글자 수가 이보다 적으면 **판이 무너졌다고 본다.**
#: 정상은 900~1,600자다. 표지처럼 짧은 쪽이 몇 장 섞이는 것은 정상이라 **비율**로 본다.
_THIN_CHARS = 300
_THIN_RATIO = 0.35


#: 한 번 잰 것을 두 번 재지 않는다 — `pdftotext` 를 쪽마다 부른다.
_MEASURED: dict[Path, tuple[int, int, int]] = {}


def _measure(pdf: Path) -> tuple[int, int, int]:
    """`(쪽수, 얇은 쪽 수, 전체 글자 수)`. 못 재면 쪽수가 `-1` 이다."""
    if pdf in _MEASURED:
        return _MEASURED[pdf]
    if shutil.which("pdftotext") is None or shutil.which("pdfinfo") is None:
        return (-1, 0, 0)
    m = re.search(r"^Pages:\s+(\d+)", _run(["pdfinfo", str(pdf)]).stdout, re.M)
    if not m:
        return (-1, 0, 0)
    pages = int(m.group(1))
    thin = total = 0
    for p in range(1, pages + 1):
        t = _run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"]).stdout.strip()
        total += len(t)
        thin += len(t) < _THIN_CHARS
    _MEASURED[pdf] = (pages, thin, total)
    return _MEASURED[pdf]


def _page_density(pdf: Path) -> tuple[int, int]:
    """`(쪽수, 쪽당 평균 글자 수)` — 사람이 보는 숫자."""
    pages, _, total = _measure(pdf)
    return (pages, total // pages if pages > 0 else 0)


def check_layout(pdf: Path) -> list[str]:
    """만들어진 PDF 가 **읽을 수 있는 판인가.**

    🔴 **이 검사가 있는 이유** — 2026-08-27 에 `docs/14` 가 77쪽으로 나왔다.
       `---` 가로줄이 표 구분자로 읽혀 문서 절반이 **폭 5.6% 짜리 한 칸 표** 안에
       갇혔고, 한글이 두 글자마다 줄바꿈됐다.

       **오류도 경고도 없었다.** PDF 는 만들어지고, 글자도 다 들어 있고, 표도 살아 있고,
       `pdftotext` 로 뽑으면 멀쩡해 보인다. *"쪽수가 많다"* 는 것만이 신호였다 —
       사람이 눈치채지 못했으면 그대로 제출됐다.

       그래서 **쪽당 글자 수**를 잰다. 판이 무너지면 이 값이 먼저 떨어진다.
    """
    pages, thin, total = _measure(pdf)
    if pages < 0:
        return [f"{pdf.name}: 쪽수를 못 읽었다 — 판 검사를 건너뛴다"]

    msgs = []
    if pages and thin / pages > _THIN_RATIO:
        msgs.append(
            f"{pdf.name}: {pages}쪽 중 {thin}쪽이 {_THIN_CHARS}자 미만이다 "
            f"(평균 {total // pages}자/쪽) — **판이 무너졌을 수 있다.** "
            f"`---` 가 표로 읽혔는지 본다"
        )
    return msgs


def build_one(src: Path, title: str, tmp: Path, write: bool) -> tuple[Path | None, int, list[str]]:
    raw = src.read_text(encoding="utf-8")
    body, drawn = render_mermaid(raw, tmp, src.stem[:2])
    body, left = to_print(body)

    # 표기 범례를 맨 앞에 둔다 — 기호만 보고는 뜻을 모른다.
    # 제목은 `-M title` 로 따로 주므로 본문이 범례로 시작해도 된다.
    body = LEGEND + "\n\n" + body

    md_path = tmp / f"{src.stem}.md"
    md_path.write_text(body, encoding="utf-8")
    if not write:
        return None, drawn, left

    out = OUT / f"{src.stem}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _run(
        [
            "pandoc", str(md_path), "-o", str(out),
            # 🔴 **`---` 를 다르게 읽는 문법 셋을 끈다.**
            #
            #    우리 문서는 절 사이를 `---` 가로줄로 나눈다. pandoc 은 그 `---` 를
            #    **세 가지로 오해할 수 있다** —
            #
            #      yaml_metadata_block  문서 중간의 `---` 도 머리말 시작으로 읽는다
            #                           → `docs/12`·`docs/14` 가 "YAML parse exception" 으로 죽었다
            #      multiline_tables     `---` 로 시작하는 **여러 줄 표**의 구분자로 읽는다
            #      simple_tables        같은 이유
            #
            #    🔴 두 번째가 **조용해서 더 나빴다.** PDF 는 정상으로 만들어지는데,
            #       `docs/14` 의 D-103 부터 끝까지가 **폭 5.6% 짜리 한 칸 표 안으로** 빨려
            #       들어가 한글이 두 글자마다 줄바꿈됐다. 77쪽 중 64쪽이 그 상태였다.
            #       오류도 경고도 없었다 — 쪽수가 이상하다는 것만이 신호였다 (2026-08-27).
            #
            #    **우리는 파이프 표만 쓴다.** 나머지 표 문법은 켜 둘 이유가 없고,
            #    켜 두면 가로줄마다 오탐이 난다. 읽는 사람을 위한 `---` 를 도구 사정으로
            #    지우는 대신 리더를 좁힌다.
            "-f", "markdown-yaml_metadata_block-multiline_tables-simple_tables",
            "--pdf-engine=xelatex", "--toc", "--toc-depth=2", "--number-sections",
            "-V", "mainfont=Noto Sans CJK KR",
            "-V", "monofont=Noto Sans Mono CJK KR",
            # 표가 넓다 — `10 §5` 는 7칸이다. 여백을 줄이고 글자를 낮춰 칸을 넓힌다.
            "-V", "geometry:margin=1.7cm",
            "-V", "fontsize=10pt",
            "-V", "linkcolor=blue", "-V", "urlcolor=blue",
            "-V", "documentclass=report",
            "-M", f"title={title}",
            # 🔴 **작성자 한 줄에 세 가지를 같이 적는다** — 통합한 사람 · 기여의 출처 · 검토자.
            #    `docs/10`~`docs/14` 머리말이 이미 이렇게 쓰고 있고, 표지만 다르게 쓰면
            #    "팀장이 혼자 썼다" 로 읽힌다. 실제로는 §11(요구사항)·§9.1(화면)·§4.4.1 이
            #    팀원 자료에서 왔다. **누가 무엇을 냈는지는 각 문서 「기여 이력」이 안다.**
            "-M", f"author={AUTHOR}",
            "-M", f"date={IMPRINT}",
            "-M", "lang=ko",
        ]
    )
    if r.returncode != 0 or not out.exists():
        print(f"  ✗ {src.name}\n{(r.stderr or '')[:400]}")
        return None, drawn, left
    return out, drawn, left


def main() -> int:
    ap = argparse.ArgumentParser(description="필수 산출물 → 제출용 PDF (생성물)")
    ap.add_argument("--write", action="store_true", help=f"{OUT.name}/ 에 기록")
    args = ap.parse_args()

    for tool in ("pandoc", "xelatex"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} 이 없다. 이 스크립트는 Linux 에서 돈다 (머리말 참조).")

    print("━━ 필수 산출물 → PDF ━━")
    if args.write and OUT.exists():
        shutil.rmtree(OUT)

    made, total_drawn, warned = [], 0, []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 표지부터. **다섯 번째 산출물이 코드라는 사실이 여기서만 보인다.**
        cover_src = tmp / "00_제출안내.md"
        cover_src.write_text(COVER, encoding="utf-8")
        out, _, left = build_one(cover_src, "제출 안내 — 필수 산출물 대조표", tmp, args.write)
        if left:
            warned.append(f"표지: {' '.join(left)}")
        print(f"  {'✓' if (out or not args.write) else '✗'} {'제출 안내 (표지·대조표)':24}"
              f"      {f'{out.stat().st_size // 1024}KB' if out else '미리 보기'}")
        if out:
            made.append(out)

        for fname, title, _req in ITEMS:
            src = DOCS / fname
            if not src.exists():
                print(f"  ✗ {fname} 가 없다")
                return 1
            out, drawn, left = build_one(src, title, tmp, args.write)
            total_drawn += drawn
            if left:
                warned.append(f"{fname}: {' '.join(left)}")
            mark = "✓" if (out or not args.write) else "✗"
            size = f"{out.stat().st_size // 1024}KB" if out else "미리 보기"
            print(f"  {mark} {title:24} 그림 {drawn}  {size}")
            if out:
                made.append(out)

    if warned:
        print("\n  ※ 대응표에 없는 이모지를 지웠다 — SYMBOLS 에 넣는다:")
        for w in warned:
            print(f"     {w}")

    print(f"\n  그림 {total_drawn}장 렌더링")
    if not args.write:
        print("\n기록하려면 --write")
        return 0

    # 🔴 **만들었다고 끝이 아니다 — 판이 무너졌는지 본다.**
    #    2026-08-27 에 `docs/14` 가 77쪽으로 나왔고 pandoc 은 아무 말도 하지 않았다.
    #    사람이 쪽수를 세어야 잡히는 결함은 다음에도 조용히 지나간다.
    broken: list[str] = []
    print("\n  ━ 판 검사 (쪽당 글자 수)")
    for pdf in made:
        msgs = check_layout(pdf)
        pages, density = _page_density(pdf)
        print(f"     {pdf.name:24} {pages:>3}쪽  {density:>5}자/쪽  {'✗' if msgs else '✓'}")
        broken += msgs
    if broken:
        print("\n  🔴 판이 무너졌다 — 이 묶음은 제출하지 않는다:")
        for b in broken:
            print(f"     {b}")
        return 1

    print(f"\n  ✓ {OUT.name}/ 에 {len(made)}개")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
