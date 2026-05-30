# teamlead

Claude Code(추후 Codex) 위에서 도는 **중간관리자 하네스**.

> 병목은 개발이 아니라 "사람과의 의사결정 대화"다.
> 의사결정을 에이전트에 위임하고, 사람에겐 **전제(premise)만 사후 보고**한다.

```
본부장(인간) ──최소 지시──▶ 팀장(teamlead) ──위임──▶ 팀원(Claude Code/Codex)
      ▲                          │
      └──── 5문장 전제보고 ◀──────┘
                 +
        무지시 시 능동: 리서치 · 모니터링 · 인사이트
```

## 행동 원칙 (코드에 인코딩됨 — `prompts/templates.py`)

1. "안 돼요" 금지 → 되는 법을 찾거나, 거절 대신 재구성 질문.
2. 사소한 트집 금지, 의심은 큰 전제 단위로.
3. 한 길만 파지 않음 → 여러 전제 병렬 탐색.
4. 지시 없어도 안 놂 → 자가 과업 생성.
5. 사용자 대면 출력은 5문장 미만, 레포트 금지, 사후 보고.

## 구조 (포트 & 어댑터)

```
teamlead/
  ports/
    worker.py        ── WorkerBackend (무거운 위임의 seam)
    thinker.py       ── Thinker (관리자 메타인지 = 작은 모델)
    retriever.py     ── Retriever (임베딩 retrieval, 우리 차별점)
  adapters/
    claude_code/     ── `claude -p` 호출·stream-json 파싱 (라이브 검증됨)
    codex/           ── `codex exec` 호출·JSONL+최종메시지 파싱 (라이브 검증됨)
    isolation.py     ── git worktree 격리 헬퍼 (병렬 전제 cwd 충돌 방지)
    artifacts.py     ── tool_use(Write/Edit) → 건드린 파일 추출 (핸드오프로 흐름)
    fake_worker.py   ── 오프라인 일꾼
    thinker/         ── fake(오프라인) / claude_cli(pip 불필요, 기본) / anthropic(haiku, SDK)
    retriever/       ── noop / embedding(multilingual-e5 + numpy)
  core/
    manager/director.py   ── 방향설정 + idle 시 자가 과업 생성  ★
    manager/premise.py    ── 전제 N개 도출 → 병렬 디스패치
    manager/reporter.py   ── 5문장 전제보고 게이트
    state/handoff.py      ── 세션 핸드오프 스키마 + 결과 흡수
    loop/scheduler.py     ── 6h 무인 롱런 루프
  prompts/templates.py    ── 명령 = 데이터 (로직과 분리)
```

핵심 seam은 `WorkerBackend`·`Thinker`·`Retriever` 세 포트. core는 이 셋만 본다 →
백엔드(Claude Code/Codex)는 어댑터만 갈아끼우면 교체된다.

## 실행

```bash
cd ~/projects/teamlead

# 오프라인 데모 (키/claude 불필요) — 전제 병렬탐색→5문장보고→핸드오프 저장
python3 -m teamlead --goal "무언가를 만든다"

# 종단 스모크 (pytest 불필요)
python3 scripts/smoke.py

# 테스트 (pip/pytest 없는 환경용 무의존 러너)
python3 scripts/run_tests.py

# 실제 동작 (claude CLI 가 PATH에 인증돼 있으면 pip 없이 바로 됨 — 라이브 검증)
python3 -m teamlead --real --backend claude --goal "..."
python3 -m teamlead --real --backend codex  --goal "..."   # 같은 포트, 백엔드만 교체

# thinker(관리자 메타인지) 백엔드: 기본 claude-cli(pip 불필요)
python3 -m teamlead --real --thinker anthropic --goal "..."  # SDK 쓰려면: pip install -e ".[thinker]"
```

## 상태

동작하는 코어 + **67개 테스트 통과**. **`--real` 전체 경로가 pip 없이 end-to-end 라이브 검증됨**
(thinker=claude-cli → 전제 도출 → 실제 claude 일꾼 병렬 → 5문장 보고 → handoff done),
**실제 claude 세션 연동 라이브 데모 성공**(격리 worktree에서 fizzbuzz.py 생성·artifacts 포착·5문장 보고 영속).
실구현 완료: 전제엔진, 디렉터(idle 자가과업·monitor 라운드로빈), 리포터(5문장 게이트),
핸드오프 흡수, 스케줄러(6h 루프·예외내성), claude_code/codex 어댑터, git worktree 격리,
artifacts 추출, ClaudeCliThinker(pip 불필요), 보고 영속성, **resume(재시작 이어가기)**.

> **이 산출물의 가치(한 문장)**: 사람이 큰 목표 한 줄만 주면, 여러 전제로 갈라 실제
> claude/codex 일꾼에게 병렬 위임하고, pip 설치 없이 돌아가, 끝나면 "무엇을 전제로
> 했는지" 5문장으로 보고하고 그 보고를 handoff.json 에 남기는 — 일꾼이 아니라 중간관리자 레이어.
> **검증된 범위**: "한 사이클 end-to-end" + 보고 영속화. 6시간 무인 실행과 resume(이어가기)은 미검증(아래 "다음").

### 적대적 리뷰 반영 (5차원 워크플로우 · 36 에이전트 · 18 confirmed)
- **[high] stderr deadlock 수정**: stdout/stderr 동시 배수(`communicate()`)로 6h 루프 멈춤 제거.
- 일꾼 기본 타임아웃 6h→30분(한 일꾼이 전체 예산 독식 방지).
- start_new_session + killpg: 타임아웃 시 손자 프로세스(MCP 등)까지 그룹 정리, 좀비 reap.
- capabilities `worktree_isolation=False` 로 정직화(미구현인데 True 광고하던 것 수정).
- stream-json 파싱: result 이벤트 없으면 assistant 텍스트 폴백.
- director: monitor 라운드로빈 + cooldown(같은 타깃 무한반복/스핀 방지), replenish 중복제거·큐 상한.
- handoff: 리스트 상한(`max_items`)으로 6h 무한증가 방지.
- reporter: 한국어(마침표 뒤 공백 없음) + 글자수 이중 게이트, surface_insight 도 동일 적용.
- scheduler: report 콜백 예외가 루프를 죽이지 않게 래핑.
- scheduler: per-cycle 데드라인(`asyncio.wait_for`) — 느린 사이클이 `max_runtime_s` 를 넘기지 못하게(실시간 테스트로 검증).

## 다음

- ~~Codex 어댑터로 seam 검증~~ ✅ 완료 (실제 `codex exec` PONG, core가 두 백엔드 구분 못 함 = 포트 증명)
- ~~worktree 격리 실제 구현~~ ✅ 완료 (`adapters/isolation.py`, git repo면 전제별 `git worktree add --detach`로 격리 cwd, 아니면 정직하게 no-op; 실제 git repo로 병렬 격리 라이브 검증)
- ~~artifacts 를 일꾼 출력에서 추출~~ ✅ 완료 (claude stream-json tool_use→파일, 라이브 검증; `artifacts.py`)
- ~~resume(이어가기)~~ ✅ 완료 (`--resume`: 같은 goal 의 handoff.json 에서 decisions/discarded/artifacts/reports 기록과 미완료 pending_requests 복원; 손상 파일·다른 goal 은 안전하게 새로 시작; E2E 크래시-재시작 검증)
- `--real` 에 `--base-repo` 인자 노출 (현재 어댑터 생성자엔 있으나 CLI 미연결 → worktree 격리 실사용 배선)
- codex artifacts 추출 (codex 의 파일변경 이벤트 스키마 확인 후 — 현재 claude 만)
- 여러 전제 병렬·6시간 무인 실행 라이브 검증 (현재 1전제·1사이클까지만 라이브 확인)
- EmbeddingRetriever 실측 (`pip install -e ".[retrieval]"`, 현재 환경 pip 없음)
