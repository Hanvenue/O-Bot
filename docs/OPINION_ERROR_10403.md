# Opinion CLOB 10403: 지역 제한 (403 Forbidden)

> errno 10403 = "API is not available to persons located in the United States, China, or restricted jurisdictions."

---

## 1. 의미

CLOB 주문 요청이 **미국·중국 등 제한 지역 IP**로 인식돼 Opinion이 403을 반환한 경우입니다.

---

## 2. 프록시가 적용되는지 확인

코드는 **CLOB Client**를 만들 때 `configuration.proxy`를 설정한 뒤, `RESTClientObject(conf)`로 HTTP 클라이언트를 새로 만들어 **모든 CLOB API 요청**(호가 조회, 주문 등)이 그 프록시를 타도록 되어 있습니다.

**서버 로그로 확인:**

- 수동 Go! 또는 자동 Go 실행 후 로그에서 다음 문구를 찾습니다.
  - `CLOB 계정 id=1: 프록시 적용됨 (host=104.250.207.162)`  
    → 이 계정의 주문 요청은 **이 호스트(프록시)**로 나갑니다.
  - `CLOB 계정 id=1: 프록시 없음` 또는 `proxy 주입 실패`  
    → 주문 요청이 **서버 IP**(예: Lightsail 프랑크푸르트)로 나갈 수 있어 403 가능성이 큽니다.

**확인 방법 예:**

```bash
sudo journalctl -u obot -n 200 --no-pager | grep -E "CLOB|프록시|10403"
```

---

## 3. 해결 방향

| 상황 | 조치 |
|------|------|
| 로그에 **"프록시 적용됨"**이 보임 | 요청은 프록시를 타고 있음. 해당 **프록시의 실제 나가는 IP**가 미국/중국으로 잡히는지 프록시 업체·대시보드에서 확인. 필요 시 다른 프록시(노르웨이/프랑스 등)로 교체. |
| **"프록시 없음"** 또는 **"proxy 주입 실패"** | .env의 `OPINION_PROXY`, `OPINION_PROXY_2` 형식 확인(예: `IP:PORT:USER:PASS`). 서버 재시작 후 다시 시도. |
| 서버가 **제한 지역**(예: 미국 리전)에 있음 | 앱을 **허용 지역 VPS**(한국, EU, 노르웨이 등)에서 돌리거나, 반드시 **프록시 적용됨** 로그가 나오는지 확인 후 해당 프록시 IP가 제한이 아닌지 확인. |

---

## 4. 서버·프록시가 유럽인데도 10403이 나올 때

| 확인 항목 | 방법 |
|-----------|------|
| **1) 주문에 쓰는 계정에 프록시가 붙어 있는지** | 브라우저에서 `https://내서버/api/opinion/clob-debug` 접속. 사용 중인 계정의 `proxy_configured`가 `true`인지 확인. 수동 Go는 보통 계정 1 사용. |
| **2) 실제로 요청이 프록시로 나가는지** | 서버 로그에서 `CLOB 계정 id=1: 프록시 적용됨 (host=...)`가 **주문 시도 직전/직후**에 한 번이라도 나오는지 확인. 없으면 프록시가 주입되지 않은 것. |
| **3) 프록시 exit IP가 제한 지역이 아닌지** | 프록시 업체 대시보드에서 exit IP 확인, 또는 `curl -x http://USER:PASS@프록시호스트:포트 https://api.ipify.org`로 나가는 IP 확인 후, 그 IP의 국가가 미국/중국/제한 지역이 아닌지 확인. “유럽 프록시”라고 해도 일부 업체는 exit가 미국이거나 데이터센터 IP로 블록될 수 있음. |
| **4) API 키/계정이 제한 지역으로 등록돼 있지 않은지** | Opinion은 **IP 외에** API 키 발급 시 기재한 지역·KYC·계정 정보로도 제한할 수 있음. 서버·프록시가 모두 유럽인데도 10403이면, [Opinion 지원](https://app.opinion.trade/terms) 또는 Terms of Use 안내에 따라 “restricted jurisdictions”에 해당 계정/키가 포함돼 있는지 문의하는 것이 좋음. |

---

## 5. VPN으로 우회하기 (서버 전체를 허용 지역 IP로 나가게)

프록시를 바꿔도 10403이면, **서버에서 나가는 IP 자체**를 허용 지역으로 바꾸는 방법입니다. 서버에 VPN 클라이언트를 깔고 **EU·한국** 등 exit으로 연결한 뒤 obot을 돌리면 됩니다.

### 5.1 준비

- VPN 업체 하나 고르기 (예: NordVPN, ExpressVPN, Proton VPN, Mullvad 등). **서버/ Linux 사용 허용**인지 약관 확인.
- 해당 업체에서 **EU 또는 한국** 서버용 설정 파일(OpenVPN `.ovpn` 또는 WireGuard `.conf`) 받기.

### 5.2 방법 A: OpenVPN (많은 업체가 제공)

```bash
# 서버 SSH 접속 후
sudo apt update && sudo apt install -y openvpn

# 업체에서 받은 .ovpn 파일을 서버로 복사한 뒤 (예: /home/ubuntu/nl.ovpn)
sudo openvpn --config /home/ubuntu/nl.ovpn --daemon

# 나가는 IP 확인 (한국/네덜란드 등이면 OK)
curl -s https://api.ipify.org
```

VPN 연결된 상태에서 obot 재시작:

```bash
sudo systemctl restart obot
```

이제 주문 요청은 VPN 터널로 나가므로, **.env 프록시 없이**도 10403이 사라질 수 있습니다. (그래도 프록시 쓰려면 그대로 두면 됨.)

### 5.3 방법 B: WireGuard (설정이 더 단순한 경우)

```bash
sudo apt update && sudo apt install -y wireguard

# 업체에서 받은 설정을 예: /etc/wireguard/wg0.conf 에 넣은 뒤
sudo wg-quick up wg0

# IP 확인
curl -s https://api.ipify.org
```

서버 재부팅 후에도 VPN 자동 연결하려면:

```bash
sudo systemctl enable wg-quick@wg0
```

### 5.4 NordVPN (전용 IP 포함) – 서버에서 스위스/EU IP 쓰기

NordVPN 계정이 있고 **전용 IP**(예: 스위스 86.38.160.227)를 쓰고 있다면, **같은 계정으로 서버(Ubuntu)에도 NordVPN을 설치**해 연결하면 서버 나가는 IP가 전용 IP로 바뀝니다.

1. **서버에 NordVPN 설치**

   ```bash
   # Ubuntu 서버 SSH 접속 후
   sh <(curl -sSf https://downloads.nordforapps.com/apps/linux/install.sh)
   ```

2. **로그인** (브라우저 링크로 인증)

   ```bash
   nordvpn login
   ```

3. **전용 IP 또는 스위스 서버로 연결**

   - 전용 IP를 Nord 계정에서 이미 설정했다면:
     ```bash
     nordvpn connect <국가코드><서버번호>   # 예: nordvpn connect ch1234 (스위스)
     ```
   - 전용 IP 서버 이름은 [Nord 계정 → Dedicated IP 설정](https://my.nordaccount.com/dashboard/nordvpn/) 또는 고객지원에서 확인.
   - 그냥 스위스 일반 서버로 연결해도 됨:
     ```bash
     nordvpn connect Switzerland
     ```

4. **나가는 IP 확인**

   ```bash
   curl -s https://api.ipify.org
   ```
   → 86.38.160.227 또는 스위스/EU 대역이면 OK.

5. **obot 재시작**

   ```bash
   sudo systemctl restart obot
   ```

이후 수동 거래 다시 시도하면 Opinion에는 **서버가 VPN으로 나가는 IP**가 보이므로 10403이 사라질 수 있습니다.

### 5.5 주의

- VPN 끄면 다시 서버 IP로 나가서 10403이 날 수 있음. 재부팅 후에는 `nordvpn connect` 또는 `openvpn`/`wg-quick up wg0` 다시 실행할지, 서비스로 등록할지 확인.
- VPN 업체 약관에서 **VPS/서버에서 사용 가능**한지 확인하는 것이 좋습니다.

---

## 6. 참고

- `core/opinion_clob_order.py`: `_get_clob_client()`에서 `conf.proxy` 설정 후 `RESTClientObject(conf)`로 교체.
- Opinion API는 요청이 들어오는 **출발 IP**로 지역을 판단합니다. 프록시를 쓰면 Opinion에는 **프록시의 exit IP**가 보입니다.
