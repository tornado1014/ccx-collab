[English](README.md) | **한국어**

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

## cc-collab CLI

`cc-collab`는 위의 셸 스크립트 및 `orchestrate.py` 워크플로를 대체하는 통합 CLI 도구입니다. [Click](https://click.palletsprojects.com/)과 [Rich](https://rich.readthedocs.io/) 기반으로 구축되었습니다.

### 설치

```bash
pip install -e .
cc-collab --version
```

### 전체 파이프라인 실행

```bash
# 시뮬레이션 모드 (실제 CLI 호출 없음)
cc-collab --simulate run --task agent/tasks/example.task.json

# 실제 CLI 연동 실행
cc-collab run --task agent/tasks/example.task.json --work-id my-feature
```

### 단계별 실행

```bash
cc-collab validate --task agent/tasks/example.task.json --out results/validation.json
cc-collab plan --task agent/tasks/example.task.json --out results/plan.json
cc-collab split --task agent/tasks/example.task.json --plan results/plan.json --out results/dispatch.json
cc-collab implement --task agent/tasks/example.task.json --dispatch results/dispatch.json --subtask-id S01 --out results/impl_S01.json
cc-collab merge --work-id demo --input "results/impl_*.json" --out results/implement.json
cc-collab verify --work-id demo --out results/verify.json
cc-collab review --work-id demo --plan results/plan.json --implement results/implement.json --verify results/verify.json --out results/review.json
cc-collab retrospect --work-id demo --review results/review.json --out results/retrospect.json
```

### 유틸리티 명령어

```bash
cc-collab health                          # CLI 도구 상태 확인
cc-collab status --work-id my-feature     # 파이프라인 진행 상태 조회
cc-collab cleanup --retention-days 7      # 오래된 결과 파일 정리
cc-collab init --task-id FEAT-001 --title "새 기능"  # 태스크 템플릿 생성
```

### 글로벌 옵션

| 옵션 | 단축키 | 설명 |
|------|--------|------|
| `--verbose` | `-v` | DEBUG 레벨 로깅 활성화 |
| `--simulate` | | 시뮬레이션 모드 (실제 CLI 호출 없음) |
| `--version` | | 버전 정보 출력 |

자세한 명령어 레퍼런스는 [docs/CC_COLLAB_CLI.md](docs/CC_COLLAB_CLI.md)를 참조하세요.

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
├── cc_collab/                      # cc-collab CLI 패키지
│   ├── __init__.py                 # 패키지 초기화 및 버전 정보
│   ├── cli.py                      # Click CLI 진입점
│   ├── bridge.py                   # orchestrate.py 브릿지 레이어
│   ├── config.py                   # 프로젝트 설정 및 플랫폼 감지
│   ├── output.py                   # Rich 기반 출력 헬퍼
│   └── commands/                   # CLI 명령어 모듈
│       ├── stages.py               # 파이프라인 단계 명령어 (8개)
│       ├── pipeline.py             # run, status 명령어
│       └── tools.py                # health, cleanup, init 유틸리티
├── tests/
│   └── test_cc_collab/             # cc-collab CLI 테스트
│       ├── test_cli.py             # CLI 진입점 테스트
│       ├── test_bridge.py          # 브릿지 레이어 테스트
│       └── test_commands.py        # 명령어 테스트
├── docs/
│   └── CC_COLLAB_CLI.md            # cc-collab CLI 레퍼런스 문서
├── .github/workflows/
│   └── agent-orchestrator.yml      # CI/CD 파이프라인
├── pyproject.toml                  # Python 패키지 설정 (cc-collab)
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

## 개발 환경 설정

### Pre-commit 훅 설치

이 프로젝트는 [pre-commit](https://pre-commit.com/)을 사용하여 커밋 시 코드 품질을 자동으로 검사합니다.

```bash
pip install pre-commit
pre-commit install
```

설치 후 `git commit`을 실행하면 다음 검사가 자동으로 수행됩니다:

- **ruff lint** -- `agent/` 및 `cc_collab/` Python 파일의 린트 검사 (E, F, W 규칙)
- **ruff format check** -- `agent/` 및 `cc_collab/` Python 파일의 포맷팅 검사
- **check-json** -- `agent/schemas/` JSON 파일의 구문 검증
- **validate-schemas** -- JSON Schema 명세 유효성 검증
- **end-of-file-fixer / trailing-whitespace** -- 파일 끝 개행 및 후행 공백 자동 수정
- **check-yaml** -- YAML 파일 구문 검증

훅 검사를 일시적으로 건너뛰어야 할 경우 `--no-verify` 플래그를 사용할 수 있습니다:

```bash
git commit --no-verify -m "긴급 수정"
```

> **참고**: `--no-verify`는 긴급 상황에서만 사용하고, 이후 반드시 `pre-commit run --all-files`로 전체 검사를 수행하세요.

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
