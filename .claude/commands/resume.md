---
description: Pull the latest state from GitHub and read the hand-off docs to continue exactly where the last session (possibly on another PC) left off
---

다른 세션이나 다른 PC에서 작업이 이어졌을 수 있다. 코드를 만지기 전에 먼저 현재 상황을 파악한다.

1. `git status`로 현재 작업 트리 상태를 확인한다. 커밋 안 된 변경사항이 있으면 **함부로 덮어쓰거나 버리지 말고**, 먼저 사용자에게 알린다 (누군가 로컬에서 작업 중이었을 수 있다).
2. `git pull --ff-only`로 원격의 최신 커밋을 가져온다. Fast-forward가 안 되면 — 로컬에 원격에 없는 커밋이 있다는 뜻이니 — 강제로 아무거나 하지 말고 상황을 사용자에게 설명하고 어떻게 할지 묻는다.
3. `CLAUDE.md` → `docs/STATE.md` → `todo.md` 순서로 읽는다 (`CLAUDE.md`가 정한 순서 그대로).
4. `docs/STATE.md`의 "지금 상태"와 "다음에 할 일"을 사용자에게 짧게 요약해서 보고한다 — 특히 "진행 중이던 작업"이 있으면 그것부터 언급한다 (다른 PC에서 뭔가 하다 만 상태일 수 있다).
5. `docs/STATE.md`의 "반드시 알아야 할 함정" 섹션도 확인해서, 이번 세션에서 같은 실수를 반복하지 않도록 한다.
6. 사용자가 다음에 뭘 하고 싶은지 묻거나, 문서에 명확한 다음 단계(예: `todo.md`의 체크 안 된 첫 항목)가 있으면 그걸 제안한다.

절대 하지 말 것: 문서를 읽기 전에 코드를 고치거나 커밋하는 것. 이 커맨드는 실행이 아니라 **상황 파악**이 목적이다 — 실제 작업은 사용자의 다음 지시를 받고 시작한다.
