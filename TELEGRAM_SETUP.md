# 📱 텔레그램 봇 설정 가이드

Auto 모드를 사용하려면 텔레그램 봇을 설정해야 합니다.

---

## 🤖 Step 1: BotFather에서 봇 생성 (3분)

### 1. 텔레그램 앱 열기

### 2. BotFather 찾기
```
검색창에 @BotFather 입력
공식 계정 클릭 (파란색 체크마크 있음)
```

### 3. 새 봇 생성
```
/newbot 입력

Bot name 입력:
예: 경봇 Gyeong Bot

Username 입력 (반드시 bot으로 끝나야 함):
예: gyeong_trading_bot

성공하면 토큰을 받습니다:
예: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 4. 토큰 복사
```
이 토큰을 안전하게 저장하세요!
절대 공유하지 마세요!
```

---

## 💬 Step 2: Chat ID 가져오기 (2분)

### 방법 1: userinfobot 사용 (쉬움)

```
1. 텔레그램 검색: @userinfobot
2. /start 클릭
3. "Id: 123456789" 복사
```

### 방법 2: 직접 확인 (조금 복잡)

```
1. 봇에게 아무 메시지 보내기
2. 브라우저에서 접속:
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   
   (YOUR_BOT_TOKEN을 실제 토큰으로 바꾸기)
   
3. JSON에서 "chat":{"id": 숫자} 찾기
4. 숫자 복사
```

---

## ⚙️ Step 3: .env 파일 설정 (1분)

```env
# .env 파일에 추가
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

**⚠️ 주의:**
- `TELEGRAM_BOT_TOKEN`: BotFather에서 받은 전체 토큰
- `TELEGRAM_CHAT_ID`: 숫자만 (따옴표 없음)

---

## ✅ Step 4: 테스트 (1분)

### 1. 앱 재시작
```bash
python app.py
```

### 2. 로그 확인
```
✅ Telegram bot initialized
✅ Telegram bot started
```

### 3. 텔레그램에서 확인
```
봇으로부터 메시지 도착:
"🤖 경봇이 시작되었습니다!"
```

---

## 📱 텔레그램 명령어

### /start
봇 시작 및 명령어 목록

### /status
현재 상태 확인
```
📊 현재 상태

Auto 모드: 🟢 실행 중
Bot 실행: ✅ Yes
```

### /stop (킬스위치!)
긴급 중지 - 모든 자동 거래 즉시 중단
```
🛑 킬스위치 활성화!

모든 자동 거래가 중지되었습니다.
```

### /resume
자동 거래 재개
```
▶️ 자동 거래 재개!

Auto 모드가 다시 활성화되었습니다.
```

### /help
도움말 표시

---

## 📨 알림 종류

### 🤖 시작/중지
```
🤖 Auto 모드 시작

Shares: 10
체크 간격: 10초
```

### 🎯 거래 가능 마켓 발견
```
🎯 거래 가능 마켓 발견

마켓: BTC/USD Up/Down 15min
방향: UP
가격 갭: +$250.00
남은 시간: 120초
```

### ✅ 거래 성공
```
✅ 거래 실행 완료

방향: UP
가격: $0.88
수량: 10 shares
시간: 14:23:45
```

### ❌ 거래 실패
```
❌ 거래 실패

에러: Insufficient balance
시간: 14:25:30
```

### ⚠️ 잔액 부족
```
⚠️ 잔액 부족

현재 잔액: $15.50
필요 금액: $20.00
```

---

## 🐛 문제 해결

### "Bot not found"
```
→ BOT_TOKEN이 잘못되었습니다
→ BotFather에서 다시 확인
```

### "Chat not found"
```
→ CHAT_ID가 잘못되었습니다
→ @userinfobot으로 다시 확인
```

### 메시지가 안 옴
```
→ 봇에게 먼저 /start 보내기
→ 봇을 차단하지 않았는지 확인
```

### "Unauthorized"
```
→ 토큰이 만료되었을 수 있음
→ BotFather에서 새 토큰 생성: /revoke
```

---

## 💡 팁

### 1. 봇 개인화
```
BotFather에서:
/setdescription - 설명 설정
/setabouttext - 소개 설정
/setuserpic - 프로필 사진 설정
```

### 2. 그룹에서 사용
```
1. 그룹 생성
2. 봇을 그룹에 초대
3. 그룹 CHAT_ID 가져오기 (음수로 시작)
4. .env에 그룹 CHAT_ID 입력
```

### 3. 알림 끄기
```
텔레그램 설정:
봇 → 알림 → 음소거
(킬스위치는 여전히 작동)
```

---

## 🎉 완료!

텔레그램 봇이 설정되었습니다!

**이제 할 수 있는 것:**
- ✅ Auto 모드 실행
- ✅ 실시간 알림 받기
- ✅ 텔레그램으로 킬스위치
- ✅ 원격 상태 확인

**다음 단계:**
1. 대시보드에서 "🤖 Auto 모드 시작" 클릭
2. 텔레그램에서 알림 확인
3. 필요시 /stop으로 중지

**화이팅!** 🚀
