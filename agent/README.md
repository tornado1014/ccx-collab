# Claude + Codex 협업 오케스트레이션

이 저장소는 `Plan → Implement → Verify → Review → Retrospect` 흐름을
맥(Plan/Review) + 윈도우(Implement)에 분리해 운영하기 위한 최소 골격을 제공합니다.

## 파일 구성
- `agent/scripts/orchestrate.py` : CLI 오케스트레이션 실행기
- `agent/schemas/` : 계약 JSON 형식
- `agent/tasks/` : 입력 작업 정의 (`*.task.json`)
- `agent/results/` : 모든 단계 산출물
- `.github/workflows/agent-orchestrator.yml` : CI 파이프라인

## 실행 전제
- GitHub repo 변수
  - `CLAUDE_CODE_CMD` : mac/review 단계에서 사용할 Claude CLI 실행 커맨드
  - `CODEX_CLI_CMD` : windows 구현 단계에서 사용할 Codex CLI 실행 커맨드
  - `VERIFY_COMMANDS` : 정적 분석/테스트 명령 배열(JSON 문자열 권장)
- CI 권장 비밀/토큰: 각 CLI에서 요구하는 인증은 해당 CLI 설정/실행 환경에 주입

## 수동 실행 예시
```bash
python agent/scripts/orchestrate.py validate-task --task agent/tasks/example.task.json --work-id demo --out agent/results/validation_demo.json
python agent/scripts/orchestrate.py run-plan --task agent/tasks/example.task.json --work-id demo --out agent/results/plan_demo.json
python agent/scripts/orchestrate.py split-task --task agent/tasks/example.task.json --plan agent/results/plan_demo.json --out agent/results/dispatch_demo.json --matrix-output agent/results/dispatch_demo.matrix.json
python agent/scripts/orchestrate.py run-implement --task agent/tasks/example.task.json --dispatch agent/results/dispatch_demo.json --subtask-id ci-cd-collab-baseline-S01 --work-id demo --out agent/results/implement_demo_ci-cd-collab-baseline-S01.json
python agent/scripts/orchestrate.py merge-results --work-id demo --kind implement --input "agent/results/implement_demo_*.json" --out agent/results/implement_demo.json
python agent/scripts/orchestrate.py run-verify --work-id demo --platform macos --out agent/results/verify_demo_macos.json
python agent/scripts/orchestrate.py run-review --work-id demo --plan agent/results/plan_demo.json --implement agent/results/implement_demo.json --verify agent/results/verify_demo_macos.json --out agent/results/review_demo.json
python agent/scripts/orchestrate.py run-retrospect --work-id demo --review agent/results/review_demo.json --out agent/retrospectives/retrospect_demo.json
```

## CI 동작 조건
- GitHub 변수 또는 워크플로우 환경 변수에서 `CLAUDE_CODE_CMD`, `CODEX_CLI_CMD`를 지정해야 합니다.
- `VERIFY_COMMANDS`는 JSON 배열 문자열(예: `["pytest -q", "npm test"]`)을 권장합니다.
- 로컬/오프라인 검증을 먼저 돌릴 때는 `SIMULATE_AGENTS=1`로 실행하면 CLI 호출 없이 더미 산출물을 생성합니다.
