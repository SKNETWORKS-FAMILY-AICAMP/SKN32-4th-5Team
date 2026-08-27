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

## 🔴 지금 이 파일들이 안고 있는 것 다섯

**받은 그대로 넣었다.** 지금 그 기계에서 도는 것과 같아야 재현이 되기 때문이다.
아래는 **다음 커밋에서 고친다** — 무엇을 바꿨는지가 이력의 diff 로 남게.

| | 무엇 | 왜 |
|---|---|---|
| ① | `/django-static/` 블록이 **없다** | `DEBUG=false` 면 Django 가 정적을 안 낸다 → **`/admin/` 이 CSS 없이 뜬다** (`10 §6.1` · `11 §6.2` · NFR-17) |
| ② | gunicorn **워커 1개** | `--workers` 가 없다. 질의 하나가 수십 초 워커를 잡는데(`12 §7`) 하나뿐이라 **두 번째 사용자는 기다린다** |
| ③ | `X-Forwarded-Proto $http_x_forwarded_proto` | 클라이언트가 보낸 헤더를 **그대로** 넘긴다. Django `SECURE_PROXY_SSL_HEADER` 가 그 값을 믿는다 — 위조하면 평문을 HTTPS 로 착각한다. 지금은 **보안그룹 하나가 막고 있다** |
| ④ | systemd 가 **MySQL 을 안 기다린다** | `After=network-online.target` 뿐. 재부팅 시 DB 보다 먼저 떠서 죽고, `Restart=on-failure` 로 살아난다 — 그 사이 502 |
| ⑤ | 업로드 상한이 **세 군데 다 다르다** | 관문 5MB · 여기 10M · `docker/nginx` 20M. 관문이 먼저 거절하니 사고는 없지만 **어디서 잘렸는지 모른다** |

> ⚠️ ③ 은 **지금 뚫려 있다는 뜻이 아니다.** ALB 보안그룹이 EC2:80 을 ALB 에서만 열어 둬서
> 외부에서 직접 못 온다 (배포계획서 §5.2). 문제는 **그 방어가 한 겹뿐이고, 왜 그래도 되는지가**
> **어디에도 안 적혀 있었다**는 것이다.

## 여기 없는 것

- **`.env`** — 비밀값은 EC2 에서만 산다 (D-29 · `12 §8`). `WorkingDirectory` 아래의 `.env` 를
  `webapp/settings.py:15` 의 `load_dotenv()` 가 읽는다
- **ALB · ACM · 보안그룹** — AWS 콘솔에 있다. 설정 내용은 `docs/lgj/02_AWS-최종-배포계획서.pdf` §4~5
- **모니터링 · 백업** — 미구성 (`NFR-23` · `NFR-24`)
