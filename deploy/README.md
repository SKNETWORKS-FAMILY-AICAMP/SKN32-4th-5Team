# `deploy/` — EC2 운영 설정

🔴 **이 폴더는 실물의 사본이다.** 여기 있는 것이 `pettriage.kro.kr` 을 실제로 돌린다.

D-107 ① 이 이것을 요구했다 — **그 기계가 죽으면 아무도 같은 것을 다시 세우지 못하는**
상태였다. 설정이 EC2 에만 있었고 git 은 몰랐다.

| 파일 | EC2 위치 |
|---|---|
| `nginx/pettriage.conf` | `/etc/nginx/sites-enabled/pettriage` |
| `systemd/pettriage-django.service` | `/etc/systemd/system/pettriage-django.service` |
| `systemd/pettriage-fastapi.service` | `/etc/systemd/system/pettriage-fastapi.service` |

`/etc/nginx/nginx.conf` 와 `mime.types` 는 **Ubuntu 기본값 그대로**라 두지 않는다.
`include /etc/nginx/sites-enabled/*` 한 줄로 위 파일을 물어 갈 뿐이다.

## `docker/nginx/nginx.conf` 와 무엇이 다른가

**둘은 다른 물건이다. 합치지 않는다** (D-107).

| | `deploy/nginx/` | `docker/nginx/` |
|---|---|---|
| 어디서 | EC2 · systemd nginx | 로컬 · 컨테이너 |
| 앞단 | **ALB 가 TLS 종단** | 없음 |
| 앱 주소 | `127.0.0.1:8000` · `:8001` | `host.docker.internal` |
| 정적 파일 | Django 가 낸다 (🔴 아래) | nginx 가 낸다 |

## 바꾸는 법

EC2 에서 고치고 여기 반영하는 것이 아니라, **여기서 고치고 EC2 에 올린다.**
반대로 하면 다시 갈라진다.

```bash
scp deploy/nginx/pettriage.conf ubuntu@<ec2>:/tmp/
sudo mv /tmp/pettriage.conf /etc/nginx/sites-enabled/pettriage
sudo nginx -t && sudo systemctl reload nginx
```

## 받은 그대로 → 고친 것 일곱

**첫 커밋은 실물 스냅샷이었다** — 지금 그 기계에서 도는 것과 같아야 재현이 되기 때문이다.
무엇을 바꿨는지는 **그 커밋과의 diff** 로 본다.

| | 무엇이었나 | 어떻게 |
|---|---|---|
| ① | `/django-static/` 블록이 **없었다** → 배포된 `/admin/` 이 CSS 없이 떴다 | `alias …/staticfiles/` 추가. **올리기 전 `collectstatic` 필수** (NFR-17) |
| ② | gunicorn **워커 1개** → 두 번째 사용자가 화면조차 못 열었다 | `--workers 3`. 2 vCPU 에 FastAPI 가 임베딩 2GB 를 상주시켜 보수적으로 |
| ③ | gunicorn `--timeout` 기본 30초 = httpx 30초와 **같아서** 경계에서 워커가 먼저 죽었다 | `--timeout 90` |
| ④ | systemd 가 **MySQL 을 안 기다렸다** → 재부팅 시 502 뒤 자동 복구 | `After=` · `Requires=mysql.service` |
| ⑤ | `/api/` 에 **`proxy_read_timeout` 이 없었다** = 기본 60초. `/api/ask` 는 수십 초 걸린다 | `180s` (로컬은 이미 그랬는데 EC2 만 없었다) |
| ⑥ | 업로드 상한이 **셋 다 달랐다** (5MB / 10M / 20M) | **10M 으로 통일.** 실질 상한은 관문 5MB |
| ⑦ | 🔴 **`/api/ask` 속도 제한이 없었다** — 무인증이고 질의당 LLM 6~7회다. `12 §10` 은 ✅ 로 닫아 뒀는데 **닫힌 것은 로컬뿐** | `limit_req` 분당 6건 · `burst=3` · 429 |

### 🔴 고치지 **않은** 것 하나 — `X-Forwarded-Proto`

`$http_x_forwarded_proto` 는 **클라이언트가 보낸 헤더를 그대로** 넘긴다.
Django `SECURE_PROXY_SSL_HEADER` 가 그 값을 믿으므로, 위조하면 평문을 HTTPS 로 착각한다.

**지금 뚫려 있다는 뜻은 아니다** — 보안그룹이 EC2:80 을 ALB 에서만 연다 (배포계획서 §5.2).
**문제는 방어가 그 한 겹뿐인데 왜 그래도 되는지가 어디에도 없었다**는 것이다.
이제 `nginx/proxy_params_pettriage` 안에 적혀 있다.

`$scheme` 로 바꾸면 **안 된다** — nginx 는 항상 `http` 로 받으므로 Django 가 HTTPS 를 모르게 되고
`SECURE_SSL_REDIRECT` 와 만나 무한 리다이렉트가 난다. 제대로 닫으려면
`set_real_ip_from <ALB 서브넷>` 이 필요하고, **대역 확인이 남았다** (`12 §10`).

## 여기 없는 것

- **`.env`** — 비밀값은 EC2 에서만 산다 (D-29 · `12 §8`). `WorkingDirectory` 아래의 `.env` 를
  `webapp/settings.py:15` 의 `load_dotenv()` 가 읽는다
- **ALB · ACM · 보안그룹** — AWS 콘솔에 있다. 설정 내용은 `docs/lgj/02_AWS-최종-배포계획서.pdf` §4~5
- **모니터링 · 백업** — 미구성 (`NFR-23` · `NFR-24`)
