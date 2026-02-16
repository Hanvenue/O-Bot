# Claude Code에 넣을 프롬프트 (Cursor 협업 규칙 자동 정리용)

아래 블록 전체를 **Claude Code**에 붙여 넣으면, Cursor와 다시 말하지 않아도 협업할 수 있는 규칙을 만들거나 갱신하게 할 수 있습니다.

---

```
이 프로젝트는 Cursor(구현)와 Claude Code(검증·정리)를 같이 씁니다. 사용자가 매번 설명하지 않아도 협업되도록, 아래를 반영한 규칙을 만들어 주세요.

1) **규칙 위치**
   - Cursor 쪽: `.cursorrules`, `.cursor/rules/` (이미 있음)
   - Claude 쪽: `.claude/rules/` 에 Cursor와 맞는 협업 규칙을 두기.
   - **단일 기준:** `docs/COLLAB_WORKFLOW.md` 가 있으면 그걸 최우선으로 하고, 없으면 이 프롬프트와 `.cursor/rules/` 내용을 합쳐서 `docs/COLLAB_WORKFLOW.md` 를 만들고, `.claude/rules/collab-cursor.md` 를 그에 맞게 작성/수정해 주세요.

2) **역할**
   - Cursor: 코드 작성·구현·리팩터링. 주석·문서는 “다른 AI가 diff만 봐도 맥락 파악” 가능하게 작성.
   - Claude Code: 코드 리뷰, PR 검토·작성. **Cursor가 만든 최신 브랜치의 `git diff`만 보고** 리뷰/PR 할 수 있어야 함.

3) **작업 흐름**
   - Cursor 작업 완료 시: 변경 요약 + **현재 브랜치명**을 남겨, Claude가 “해당 브랜치 diff만 보고 작업”할 수 있게 함.
   - Claude는 사용자가 “Cursor로 작업한 최신 브랜치에서 diff만 보고 ~ 해 줘”라고 하면, 그 브랜치의 `git diff`를 기준으로 리뷰/PR 수행.

4) **규칙 동기화**
   - `.cursor/rules/` 와 `.claude/rules/` 의 협업 관련 내용이 어긋나지 않게, `docs/COLLAB_WORKFLOW.md` 를 기준으로 맞추기.
   - 이번 대화에서 만든/수정한 규칙 내용을 요약해 주고, 필요하면 “이걸 Cursor 쪽 .cursorrules 에도 반영하면 좋다”는 제안만 해 주세요 (직접 수정은 안 해도 됨).
```

---

## 사용 방법

1. 위 **세 개의 백틱(` ``` `) 사이 전체**를 복사합니다.
2. Claude Code 채팅에 붙여 넣고 전송합니다.
3. Claude Code가 `docs/COLLAB_WORKFLOW.md` 생성/갱신, `.claude/rules/collab-cursor.md` 작성·수정을 해 줍니다.
4. 이후에는 “Cursor로 작업한 브랜치에서 diff만 보고 리뷰해 줘”처럼만 말해도, 이 규칙대로 동작하도록 할 수 있습니다.
