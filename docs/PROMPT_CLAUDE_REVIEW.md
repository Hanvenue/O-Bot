# Claude Code 검토 요청용 프롬프트

아래 블록을 **그대로 복사**해서 Claude Code에 붙여 넣으면 됩니다.

---

## 브랜치명

```
feat/env-template
```

---

## 검토 요청 프롬프트 (복사용)

```
O-Bot 프로젝트 코드 리뷰 부탁해.

**브랜치:** feat/env-template (main 대비)

**규칙:** 이 레포의 docs/COLLAB_WORKFLOW.md 를 보면 돼. Cursor가 구현하고, 너(Claude Code)는 해당 브랜치의 diff만 보고 코드 리뷰 또는 PR 검토/작성 담당이야.

**요청:**
1. feat/env-template 브랜치에서 main(또는 기본 브랜치) 대비 git diff 를 확인해 줘.
2. 변경된 코드에 대해 코드 리뷰 해 줘. (버그·보안·일관성·문서 반영 여부 등)
3. PR 올릴 때 쓸 수 있게, 변경 요약 + 리뷰 요약을 정리해 줘. (원하면 PR 설명문 초안도 작성해 줘.)

**수정 사항 상세:** docs/CHANGES_FOR_CLAUDE_REVIEW.md 에 전부 정리해 두었어. 참고해서 리뷰해 줘.

**요약 (참고용):**
- .env/계정: get_env_accounts()로 계정 N개(1~20) 확장. env.template 추가, .env.example 정리.
- 계정 2 IP 안 나오던 문제: _proxy_display_host, _ensure_env_loaded, get_all() 시 _load() 재호출로 수정.
- CLOB/실시간 자전거래: Taker MARKET, Maker 직후 0.2초, GAP 200달러 기준 Maker 방향, UI GAP 표시.
- 문서: CLOB_WASH_TRADE_REVIEW, PROXY_TROUBLESHOOTING, 현재_작업_상태 등.

O-Bot만 대상이고, 경봇(gyeong-bot) 쪽은 건드리지 않았어.
```

---

위 프롬프트를 Claude Code 채팅에 붙여 넣고 전송하면, 브랜치 diff 기준으로 리뷰·PR 초안을 받을 수 있습니다.
