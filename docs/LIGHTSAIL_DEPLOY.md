# Lightsail 배포 가이드 (오봇 O-Bot)

오봇을 AWS Lightsail에 배포하는 방법입니다. Vercel과 달리 **자동 거래 포함 전체 기능**이 동작합니다.

---

## 인스턴스 정보

| 항목 | 값 |
|------|----|
| **리전** | 프랑크푸르트 (eu-central-1) |
| **OS** | Ubuntu 22.04 LTS |
| **플랜** | $10/mo (2GB RAM) |
| **Static IP** | 18.198.188.126 |
| **접속 URL** | http://18.198.188.126 |

---

## Vercel 대비 기능 비교

| 기능 | Vercel | Lightsail |
|------|--------|-----------|
| 접속 암호 로그인 | ✅ | ✅ |
| Opinion 대시보드 (다중 로그인) | ✅ | ✅ |
| API (마켓, 수동 거래, BTC 갭 등) | ✅ | ✅ |
| **자동 거래 (Auto)** | ❌ | ✅ |
| **BTC 실시간 스트림** | REST fallback만 | ✅ |

---

## 서버 구조

- **프로세스 관리:** systemd (`/etc/systemd/system/obot.service`)
- **앱 서버:** gunicorn (`127.0.0.1:5000`)
- **웹 서버:** nginx (포트 80, 리버스 프록시)
- **앱 경로:** `/home/ubuntu/O-Bot`
- **venv 경로:** `/home/ubuntu/O-Bot/venv`

---

## 최초 배포 절차

### 1. SSH 접속

```bash
ssh -i ~/Downloads/LightsailDefaultKey-eu-central-1.pem ubuntu@18.198.188.126
```

### 2. 앱 배포

```bash
git clone https://github.com/Hanvenue/O-Bot.git
cd O-Bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 3. .env 설정

```bash
cp .env.example .env
nano .env
```

필수값:
- `OPINION_API_KEY`, `OPINION_PROXY`, `OPINION_DEFAULT_EOA`
- `SECRET_KEY` — 긴 랜덤 문자열
- `FLASK_ENV=production`, `FLASK_DEBUG=False`

### 4. systemd 서비스 등록

```bash
sudo nano /etc/systemd/system/obot.service
```

```ini
[Unit]
Description=O-Bot Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/O-Bot
EnvironmentFile=/home/ubuntu/O-Bot/.env
ExecStart=/home/ubuntu/O-Bot/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 90 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable obot
sudo systemctl start obot
```

### 5. nginx 설정

```bash
sudo nano /etc/nginx/sites-available/obot
```

```nginx
server {
    listen 80;
    server_name 18.198.188.126;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/obot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 코드 업데이트 방법 (서버 반영)

코드 수정 후 **서버에 반영할 때**:

```bash
cd /home/ubuntu/O-Bot
git pull origin main
sudo systemctl restart obot
```

---

## 보안

- **접근 제어:** Lightsail 방화벽에서 허용 IP만 80포트 오픈 권장
- **HTTPS:** 도메인 연결 시 Let's Encrypt로 SSL 적용 가능
- **현재:** IP 화이트리스트로 접근 제한 운영 중

---

## 문제 해결

```bash
# 앱 상태 확인
sudo systemctl status obot

# 앱 로그 확인
sudo journalctl -u obot -f

# nginx 로그 확인
sudo tail -f /var/log/nginx/error.log
```

### "1시간 마켓 없음"이 뜰 때

- **원인:** 서버에서 Opinion API로 시장 목록을 가져오지 못함.
- **확인:** 서버의 `/home/ubuntu/O-Bot/.env`에 `OPINION_API_KEY`, `OPINION_PROXY`(계정 1)가 설정되어 있는지 확인.
- **프록시:** Opinion이 지역 제한이 있으면, Lightsail(프랑크푸르트)에서 접속하려면 **프록시가 필요**할 수 있음. 같은 .env를 로컬에서 쓰고 있다면 서버에도 동일하게 넣어 두세요.
- **로그:** `sudo journalctl -u obot -n 100` 로 get_markets 실패/타임아웃 메시지가 있는지 확인.
