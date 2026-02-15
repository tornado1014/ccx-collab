# Claude Code + Codex CLI 협업 시스템

Claude Code CLI(설계자)와 Codex CLI(빌더)가 협력하여 자동화된 개발 파이프라인을 실행하는 CI/CD 협업 시스템입니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Runner                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Validate │→ │   Plan   │→ │  Split   │→ │ Implement  │  │
│  │   Task   │  │ (Claude) │  │   Task   │  │(Claude/    │  │
│  └──────────┘  └──────────┘  └──────────┘  │ Codex)     │  │
│                                            └──────┬─────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │        │
│  │Retrospect│← │  Review  │← │  Verify  │← ───────┘        │
│  │          │  │  (Gate)  │  │  (Test)  │  Merge Results   │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 주요 특징

- **역할 기반 라우팅**: `architect`(Claude) / `builder`(Codex) 역할에 따라 자동으로 CLI 도구 선택
- **자동 청크 분할**: 30-90분 단위로 구현 작업을 자동 분할
- **크로스 플랫폼**: macOS/Windows 동시 지원 (GitHub Actions CI)
- **시뮬레이션 모드**: `SIMULATE_AGENTS=1`로 CLI 호출 없이 파이프라인 검증
- **품질 게이트**: Plan → Implement → Verify → Review 각 단계의 통과 조건 엄격 관리

## 빠른 시작

### 설치

```bash
git clone <repository-url>
cd Claude_Codex_Collaboration
pip install -r requirements.txt
```

### 시뮬레이션 모드 실행 (CLI 불필요)

```bash
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id demo
```

### 실제 CLI 연동 실행

```bash
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]'

./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json \
  --work-id my-work
```

### 단계별 수동 실행

```bash
# 1. 태스크 검증
python3 agent/scripts/orchestrate.py validate-task \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/validation_demo.json

# 2. 계획 수립 (Claude)
python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json --work-id demo \
  --out agent/results/plan_demo.json

# 3. 태스크 분할
python3 agent/scripts/orchestrate.py split-task \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json

# 4. 구현 (Codex/Claude)
python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id demo-S01 --work-id demo \
  --out agent/results/implement_demo_S01.json

# 5. 결과 병합
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --out agent/results/implement_demo.json

# 6. 검증
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo --platform mac \
  --out agent/results/verify_demo.json

# 7. 리뷰 게이트
python3 agent/scripts/orchestrate.py run-review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo.json \
  --out agent/results/review_demo.json

# 8. 회고
python3 agent/scripts/orchestrate.py run-retrospect \
  --work-id demo --review agent/results/review_demo.json \
  --out agent/results/retrospect_demo.json
```

## 프로젝트 구조

```
├── agent/
│   ├── scripts/
│   │   ├── orchestrate.py          # 핵심 오케스트레이션 엔진
│   │   ├── pipeline-runner.sh      # 전체 파이프라인 실행기 (bash)
│   │   ├── pipeline-runner.ps1     # Windows PowerShell 실행기
│   │   ├── claude-wrapper.sh       # Claude CLI 래퍼
│   │   └── codex-wrapper.sh        # Codex CLI 래퍼
│   ├── schemas/                    # JSON 스키마 계약
│   │   ├── task.schema.json
│   │   ├── cli-envelope.schema.json
│   │   ├── plan-result.schema.json
│   │   ├── implement-result.schema.json
│   │   └── review-result.schema.json
│   ├── tasks/                      # 입력 태스크 정의
│   ├── tests/                      # pytest 테스트 스위트
│   └── pipeline-config.json        # 파이프라인 설정
├── .github/workflows/
│   └── agent-orchestrator.yml      # CI/CD 파이프라인
├── CLAUDE.md                       # Claude Code 지침
├── AGENTS.md                       # 에이전트 역할 정의
└── requirements.txt                # Python 의존성
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `CLAUDE_CODE_CMD` | Claude Code CLI 실행 명령어 | (필수) |
| `CODEX_CLI_CMD` | Codex CLI 실행 명령어 | (필수) |
| `VERIFY_COMMANDS` | 검증 명령어 (JSON 배열 문자열) | pipeline-config.json 참조 |
| `SIMULATE_AGENTS` | 시뮬레이션 모드 (`1`=활성) | `0` |
| `AGENT_MAX_RETRIES` | CLI 호출 최대 재시도 횟수 | `2` |
| `AGENT_RETRY_SLEEP` | 재시도 대기 시간 (초) | `20` |

## 테스트

```bash
# 전체 테스트 실행
python3 -m pytest agent/tests/ -v

# E2E 시뮬레이션 테스트
SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh \
  --task agent/tasks/example.task.json --work-id test-e2e
```

## 라이선스

이 프로젝트는 [MIT 라이선스](LICENSE)로 배포됩니다.
