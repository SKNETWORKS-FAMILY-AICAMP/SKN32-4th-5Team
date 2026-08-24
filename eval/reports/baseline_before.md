# 전환 전 기준선 — 골든셋 60건

> **SKN 4차 단위 프로젝트** · 0단계 (14 §5 · D-102)
> `scripts/freeze_baseline.py` 가 만든다. **손으로 고치지 않는다.**

이 숫자는 성능 주장이 아니라 **비교 기준점**이다. 8단계(회귀 확인)는
전환 후 수치를 여기와 맞대고, **소음대 안이면 같다고 읽는다.**

## 1. 무엇을 잰 것인가

| 항목 | 값 |
|---|---|
| 커밋 | `43264e3d88b5` |
| 커밋 안 된 변경 | 없음 |
| 비교군 | `--arm A` |
| 엔진 · 모델 | graph · api:gpt-4o-mini |
| 임베딩 | BAAI/bge-m3 · top_k 5 |
| 프로파일 | eval · max_clarify_turns 2 |
| 판 수 | 2판 (10.0분, 9.4분) |

## 2. 소음대 — 같은 코드로 몇 건이 흔들리나

| 판 | 통과 | 통과율 |
|---|---|---|
| 1 | 37/60 | 61.7% |
| 2 | 38/60 | 63.3% |

**소음대 ±1건 (±1.7pp)** — 통과가 갈린 건 1건 (G-018)

> 🔴 **전환 후 차이가 이 폭 안이면 "달라졌다"고 말하지 않는다.**
> 밖이면 `scripts/diff_reports.py` 로 어느 건이 어디로 갔는지 먼저 본다 —
> 총계만 보면 방향을 못 읽는다 (틀리던 건이 거절로 빠져도 일치도는 오른다).

## 3. 판 사이에서 움직인 케이스

| case_id | 무엇이 | 판별 값 |
|---|---|---|
| G-018 | passed | False → True |
| G-018 | actual_level | 4 → 3 |
| G-018 | llm_level | 4 → 1 |
| G-106 | actual_status | refused → clarify |

**`llm_level` 만 갈리고 `passed` 는 안 갈린 건**은 결함이 아니라 증거다 —
규칙 바닥과 게이트가 LLM 의 흔들림을 흡수했다는 뜻이다 (D-09 · 04b).

## 4. 8단계에서 할 일

```powershell
python eval/harness/run_eval.py --arm A --json eval/reports/baseline_after.json
python scripts/diff_reports.py eval/reports/baseline_before.json eval/reports/baseline_after.json
```

판정: 통과 건수 차이가 **1건 이하**면 동일로 읽는다. 그보다 크면 뒤집힌 케이스를 전수로 설명한 뒤에 병합한다 (D-102).
