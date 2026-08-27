.PHONY: help doctor install initdb serve test todo lint fmt verify facts golden eval baseline submit submit-check rules vocab index train up db down docker clean

help:            ## 이 목록
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

doctor:          ## 새 기계에서 돌 준비가 됐나 (환경·키·인덱스 점검. 고치지는 않는다)
	python scripts/doctor.py

initdb:          ## DB 스키마 생성 (DATABASE_URL 필요). 기동 시 자동 실행하지 않는다
	python -m pettriage.app.database

install:         ## 개발 환경 설치 (GPU 없이 API·테스트까지)
# 🔴 `db` 를 빼지 않는다 — 없으면 tests/test_auth_api.py 가 모듈째 건너뛰어
#    인증·프로필 25건이 조용히 안 돈다 (요약줄엔 `1 skipped` 로만 보인다).
	pip install -e '.[api,rag,ingest,db,dev]' -c constraints.txt
	@git rev-parse --git-dir >/dev/null 2>&1 \
		&& pre-commit install \
		|| echo "· git 저장소가 아니라 pre-commit 훅은 건너뛴다 (설치는 완료)"

serve:           ## FastAPI + 데모 프론트 → http://127.0.0.1:8000
	uvicorn pettriage.app.main:app --reload --app-dir src

test:            ## 안전 장치 회귀 테스트
	pytest

todo:            ## 남은 일 목록 — 구현하면 초록이 된다
	pytest -m todo

# `eval` 을 뺐더니 하네스 800여 줄이 린트 밖에 있었다 (2026-08-02).
LINT_PATHS = src tests scripts eval

lint:            ## 정적 검사
	ruff check $(LINT_PATHS)
	ruff format --check $(LINT_PATHS)

fmt:             ## 자동 정리
	ruff check --fix $(LINT_PATHS)
	ruff format $(LINT_PATHS)

verify:          ## 층 0 — 코퍼스 정합성 + 자료 유출 확인
	python scripts/verify_corpus.py
	bash scripts/check_no_data.sh

facts:           ## 사실 표 검사 (WS1) — 01e 지침
	python scripts/check_facts.py

golden:          ## 골든셋 검사 (WS4) — 04a 지침
	python scripts/check_goldenset.py

reqs:            ## 요구사항 정의서 정합성 (1단계) — 추적표 참조가 이어지는가
	python scripts/check_requirements.py

docs-check:      ## 산출물 문서가 주장하는 값이 실물과 같은가 (--tests 로 테스트 수까지)
	python scripts/check_requirements.py
	python scripts/check_docs.py
	python scripts/check_submission.py

reqs-xlsx:       ## 요구사항정의서 → 제출용 xlsx 재생성 (생성물이다. 손으로 고치지 않는다)
	python scripts/check_requirements.py
	python scripts/build_requirements_xlsx.py --write

submit-pdf:      ## 필수 산출물 → 제출용 PDF 묶음 (생성물 · Linux 전용)
	python scripts/build_submission_pdf.py --write

# 🔴 `제출_4차/` 는 **커밋한다** (D-111) — 저장소로 제출하기 때문이다.
#    그래서 낡을 수 있고, 낡으면 아무도 모른다 (PDF 는 diff 가 안 된다).
#    이 검사가 `docs/` 해시와 대조한다. `make docs-check` 와 CI 가 부른다.
submit-check:    ## 커밋된 제출 PDF 가 지금 docs/ 와 같은가 (Windows 에서도 돈다)
	python scripts/check_submission.py

testplan-xlsx:   ## 테스트계획 → 제출용 xlsx 재생성 (생성물이다. 손으로 고치지 않는다)
	python scripts/build_testplan_xlsx.py --write

rules:           ## 사실 표 → 규칙 테이블 재생성 (생성물이다. 손으로 고치지 않는다)
	python scripts/build_rule_table.py --write

vocab:           ## 사실 표 → 물질 어휘 폐쇄 목록 재생성 (D-59 ①. 생성물이다)
	python scripts/build_vocabulary.py --write

# 산출물 ④의 실행 진입점. 예전에는 Makefile 에 없어서 CI 에 배선할 자리도 없었다.
# 게이트 기본값은 보수적으로 둔다 — 분모가 작으면 비율이 무의미하다.
# ⚠️ `make eval --engine graph` 는 안 된다 — make 가 자기 플래그로 먹는다.
#    엔진은 **프로파일이 정한다** (`configs/eval.yaml` 의 serve.engine: graph).
eval:            ## 골든셋 평가 (정확도 + 지연). 게이트 포함
	PETTRIAGE_PROFILE=eval python eval/harness/run_eval.py --json eval/reports/latest.json \
		--fail-under 0.05 --fail-missed 0.30 --min-graded 10

# 0단계 — Django 전환에 손대기 전 기준선. **전환 뒤에는 다시 잴 수 없다** (14 §5 · D-102).
# 판을 두 번 도는 이유는 소음대다 — `seed` 가 없어 같은 코드도 결과가 흔들리고,
# 그 폭을 모르면 8단계에서 나온 차이가 전환 탓인지 소음인지 못 가른다.
baseline:        ## 0단계 · 전환 전 기준선 고정 (2판 + 소음대). 약 15분
	python scripts/freeze_baseline.py

# 필수 산출물 넷을 `제출/` 한 폴더로 모은다. **손으로 모으지 않는다** —
# 사본이 원본과 어긋나는 순간 어느 쪽이 진짜인지 알 수 없게 된다 (D-22).
# `제출/` 은 커밋하지 않는다. 제출은 `make submit-zip` 이 만든 묶음을 올린다.
submit:          ## 필수 산출물 넷을 제출/ 폴더로 모은다 (생성물이다)
	python scripts/make_submission.py

submit-zip:      ## 제출/ + 제출_<커밋>.zip
	python scripts/make_submission.py --zip

index:           ## 사실 표 → 청크 **+ Chroma 적재** (D-44)
	python scripts/build_index.py --store chroma

train:           ## Qwen3-4B QLoRA 학습 (GPU 필요)
	PETTRIAGE_PROFILE=train python -m pettriage.models.training.qlora \
		--data data/train/samples.jsonl --out artifacts/adapters/qwen3-4b-mt

up:              ## API + MySQL 기동
	docker compose up --build

db:              ## MySQL 만 기동 — 로컬에 설치하지 않는다 (D-48)
	docker compose up -d db

down:            ## 컨테이너 정리
	docker compose down

docker:          ## API 이미지만 빌드
	docker build -t pettriage-api .

clean:           ## 캐시·빌드 산출물 삭제
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov build dist *.egg-info
