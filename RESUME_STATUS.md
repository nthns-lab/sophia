# SOPHIA — 작업 재개 메모 (2026-05-31)

## 지금 하던 일: 사용자 서술의 신규 3기능 구현 (커밋 금지, 사용자 리뷰 대기 중)

대화 중 거대 병렬-취소로 anticipation 작업이 롤백됐다가 재적용 중. 현재 상태:

### ① 리소스 거버너 — 완료
- `sophia/ports/resource.py`, `adapters/resource/{system,fake}.py` 생성됨.
- scheduler `_explore`가 `governor.concurrency()`로 `dispatch_parallel(max_concurrency=)` 호출. premise.py에 세마포어 추가됨.
- 테스트: test_resource.py, test_resource_wiring.py 통과.

### ② Notifier(이메일 보고) — 완료
- `sophia/ports/notifier.py`, `adapters/notifier/{email_smtp,stdout,fake}.py` 생성됨.
- scheduler `_persisting_report`가 `notifier.send()` 호출, `_report_subject()` 있음.
- 테스트: test_notifier.py 통과.
- ⚠️ 단 test_notifier.py가 직전 롤백으로 디스크에 있는지 재확인 필요(git status에 안 보였음).

### ③ anticipation(반응 예측→선제작업) — 재적용 중, 미완
완료된 것:
- `sophia/core/manager/anticipation.py` 생성됨 (anticipate 함수).
- `prompts/templates.py`에 ANTICIPATE/ANTICIPATE_SCHEMA 추가됨(방금 적용, 검증 필요).
- scheduler.py import에 Notifier/ResourceGovernor/anticipate 추가됨(타입힌트 런타임 해석 OK 확인).

**아직 안 된 것 (scheduler.py에 재적용 필요 — 롤백으로 사라짐):**
1. Scheduler 데이터클래스 필드 추가:
   ```
   anticipate: bool = False
   anticipation_width: int = 2
   max_speculative: int = 20
   speculative_requests: list[str] = field(default_factory=list)
   ```
2. `_cycle()`에 speculative 큐 분기 추가: pending_requests → speculative_requests → director.next_task 순. _explore 호출 시 `speculative=` 인자 전달.
3. `_explore(self, request, ho, report, speculative=False)` 시그니처 + 끝에:
   ```
   summary = await to_premise_report(...)
   report(summary)
   if self.anticipate and not speculative:
       await self._anticipate(summary, ho)
   ```
   그리고 `_anticipate(self, report_summary, ho)` 메서드 추가(anticipate 호출, max_speculative-len 만큼 speculative_requests.extend).
4. run()의 영속화 두 곳에 `ho.speculative_requests = list(self.speculative_requests)` 추가.
5. `_init_handoff`에 speculative_requests 복원 추가.
6. handoff.py: `speculative_requests: list[str] = field(default_factory=list)` 필드 추가됨? — 재확인.
7. __main__.py: `_build_notifier()`, build_real에 governor=SystemResourceGovernor()/notifier/anticipate 와이어링, `--anticipate` argparse. — 롤백됐는지 재확인.
8. 테스트: tests/test_anticipation.py 작성(아래 스펙). depth-1, max_speculative 상한, resume 영속, off-by-default 검증.

### 검증 명령 (sophia 디렉토리에서)
```
cd /home/younjihoon/projects/sophia
python3 -m compileall -q sophia tests scripts
python3 scripts/run_tests.py   # 무의존 러너
python3 scripts/smoke.py
```
- 직전 안정 상태: 84 passed (governor+notifier 포함, anticipation 제외).
- anticipation까지 다 되면 ~98 목표.

### 라이브 검증(이미 1회 성공했음, 재현용)
실제 claude로 anticipation: 실제요청→보고→예측2개→선제실행→큐소진 전부 fired 확인됨.
단 toy goal(PONG)이라 예측 '내용'은 빈약 — 품질은 풍부한 목표로 재검증 필요.

## 환경 주의
- pip/pytest 없음, python3 시스템만. psutil 5.9.8은 있음. smtplib stdlib.
- Bash cwd 가끔 리셋 → 명령마다 `cd /home/younjihoon/projects/sophia &&` 권장.
- 거대 병렬 도구호출 금지(실패 probe가 전체 배치를 취소시킴). 작게 순차로.

## 리모트
- github.com/nthns-lab/sophia (public, main). 최신 푸시는 resume/base-repo까지(67테스트 시점).
- 3기능은 아직 미커밋·미푸시 — 사용자가 "읽고 피드백" 후 커밋 예정.

## README
- 이미 SOPHIA 철학 중심으로 재작성됨 + 3기능 반영분 일부 적용(how-it-works 8단계, 포트 5개, --anticipate 예시, 상태 98테스트로 갱신). scheduler 재적용 끝나면 테스트 수만 실제와 맞추면 됨.
