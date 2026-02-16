[English](README.md) | **한국어**

# Agent Orchestration API Reference

Claude Code CLI(architect)와 Codex CLI(builder)가 협력하여 자동화된 개발 파이프라인을 실행하는 오케스트레이션 엔진의 상세 API 레퍼런스입니다.

> 전체 시스템 개요 및 빠른 시작은 [루트 README.md](../README.md)를 참조하세요.

---

## 목차

1. [API Reference](#api-reference)
   - [validate-task](#1-validate-task)
   - [run-plan](#2-run-plan)
   - [split-task](#3-split-task)
   - [run-implement](#4-run-implement)
   - [merge-results](#5-merge-results)
   - [run-verify](#6-run-verify)
   - [run-review](#7-run-review)
   - [run-retrospect](#8-run-retrospect)
2. [Schema Reference](#schema-reference)
3. [Troubleshooting Guide](#troubleshooting-guide)
4. [Configuration Reference](#configuration-reference)

---

## API Reference

모든 action은 `orchestrate.py`의 subcommand로 실행됩니다.

```bash
python3 agent/scripts/orchestrate.py [--verbose] <action> [options]
```

글로벌 옵션:

| 옵션 | 설명 |
|------|------|
| `--verbose`, `-v` | DEBUG 레벨 로깅 활성화 |

### Exit Code 규칙

| Exit Code | 의미 |
|-----------|------|
| `0` | 성공 |
| `1` | 입력 오류 (파일 미존재, JSON 파싱 실패, 필수 파라미터 누락) |
| `2` | 로직 실패 (validation error, CLI 실패, 품질 게이트 미통과) |

---

### 1. validate-task

태스크 JSON 파일의 유효성을 검증합니다. `task.schema.json`에 대한 스키마 검증과 필수 필드 정규화를 수행합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--task` | Yes | - | 태스크 JSON 파일 경로 |
| `--work-id` | No | `""` | 작업 식별자 (미지정 시 task_id 사용) |
| `--out` | No | `agent/results/validation_{task_id}.json` | 결과 출력 경로 |

#### 출력 형식

```json
{
  "agent": "validation",
  "work_id": "my-task-001",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready",
  "validation_errors": [],
  "task": { "...normalized task object..." }
}
```

`status` 값:
- `"ready"` -- 검증 통과, 파이프라인 진행 가능
- `"blocked"` -- validation_errors 존재, 수정 필요

#### 정규화 동작

- `task_id` 누락 시 `"task-unknown"` 자동 할당
- `subtasks`가 문자열 배열이면 object 형태로 변환
- `platform` 값을 `["mac", "windows", "both"]` 범위로 정규화
- `subtask_id` 미지정 시 `{task_id}-S{01,02,...}` 패턴으로 자동 생성

#### 실행 예시

```bash
python3 agent/scripts/orchestrate.py validate-task \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/validation_demo.json
```

---

### 2. run-plan

Claude Code CLI를 호출하여 태스크를 30-90분 단위의 implementation chunk로 분해하는 계획을 수립합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--task` | Yes | - | 태스크 JSON 파일 경로 |
| `--work-id` | No | task_id | 작업 식별자 |
| `--out` | Yes | - | 계획 결과 출력 경로 |

#### 사용 환경 변수

| 변수 | 용도 |
|------|------|
| `CLAUDE_CODE_CMD` | Claude CLI 실행 명령어 (미설정 시 `SIMULATE_AGENTS=1` 필요) |
| `SIMULATE_AGENTS` | `1` 설정 시 CLI 호출 없이 시뮬레이션 실행 |

#### 출력 형식

```json
{
  "agent": "claude",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "implementation_contract": ["criterion 1", "criterion 2"],
  "test_plan": ["pytest -v", "flake8"],
  "open_questions": [],
  "chunks": [
    {
      "chunk_id": "demo-C01",
      "title": "Add orchestrator schemas",
      "estimated_minutes": 60,
      "role": "builder",
      "depends_on": [],
      "scope": "implementation",
      "files_affected": ["agent/schemas/*.json"],
      "acceptance_criteria": [
        {
          "id": "AC-S01-1",
          "description": "Schema files are valid JSON",
          "verify_command": "python3 -c \"import json...\"",
          "verify_pattern": "",
          "category": "functional"
        }
      ],
      "source_subtask_id": "demo-S01"
    }
  ],
  "machine_readable_criteria": [],
  "cli_output": { "...raw CLI response..." }
}
```

`status` 값:
- `"done"` -- 계획 수립 완료
- `"blocked"` -- CLI 실패 또는 결과 파싱 불가

#### Chunk 분할 로직

1. CLI가 구조화된 `chunks` 배열을 반환하면 그대로 사용
2. 그렇지 않으면 태스크의 subtasks에서 자동 생성:
   - `estimated_minutes <= 90`: 단일 chunk
   - `estimated_minutes > 90`: 90분 단위로 자동 분할 (acceptance_criteria도 분배)
   - 최소 30분, 최대 90분으로 클램핑

#### 실행 예시

```bash
# 시뮬레이션 모드
SIMULATE_AGENTS=1 python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json

# 실제 CLI 연동
CLAUDE_CODE_CMD="claude --print" python3 agent/scripts/orchestrate.py run-plan \
  --task agent/tasks/example.task.json \
  --work-id demo \
  --out agent/results/plan_demo.json
```

---

### 3. split-task

계획 결과(plan)를 기반으로 subtask별 dispatch 파일을 생성합니다. 각 subtask에 `role`(architect/builder)과 `owner`(claude/codex)를 할당합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--task` | Yes | - | 태스크 JSON 파일 경로 |
| `--plan` | No | `""` | run-plan 결과 파일 경로 (미지정 시 태스크 subtasks만 사용) |
| `--out` | Yes | - | dispatch 결과 출력 경로 |
| `--matrix-output` | No | `""` | CI matrix용 JSON 출력 경로 (간략한 subtask 목록) |

#### 출력 형식 (dispatch)

```json
{
  "agent": "dispatch",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "plan_version": "v1",
  "subtasks": [
    {
      "subtask_id": "demo-S01",
      "title": "Add orchestrator schemas and scripts",
      "role": "builder",
      "owner": "codex",
      "scope": "implementation",
      "estimated_minutes": 60,
      "depends_on": [],
      "files_affected": ["agent/schemas/*.json"],
      "acceptance_criteria": [],
      "notes": [],
      "work_id": "demo",
      "risk_level": "medium",
      "source_subtask_id": null
    }
  ],
  "dispatch_from_plan": {
    "implementation_contract": [],
    "test_plan": []
  }
}
```

#### Matrix 출력 형식

`--matrix-output`을 지정하면 CI parallel job dispatch에 사용할 수 있는 간략 배열을 출력합니다:

```json
[
  {
    "subtask_id": "demo-S01",
    "role": "builder",
    "owner": "codex",
    "estimated_minutes": 60,
    "depends_on": []
  }
]
```

#### Role 결정 우선순위

1. `subtask.role` 필드가 `"architect"` 또는 `"builder"`이면 그대로 사용
2. `subtask.owner == "claude"` -> `architect`
3. `subtask.owner == "codex"` -> `builder`
4. 기본값: `builder`

#### 실행 예시

```bash
python3 agent/scripts/orchestrate.py split-task \
  --task agent/tasks/example.task.json \
  --plan agent/results/plan_demo.json \
  --out agent/results/dispatch_demo.json \
  --matrix-output agent/results/dispatch_demo.matrix.json
```

---

### 4. run-implement

dispatch된 개별 subtask를 해당 역할의 CLI 에이전트(Claude 또는 Codex)로 실행합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--task` | Yes | - | 태스크 JSON 파일 경로 |
| `--dispatch` | No | `""` | dispatch 파일 경로 (split-task 결과) |
| `--subtask-id` | Yes | - | 실행할 subtask ID |
| `--work-id` | No | task_id | 작업 식별자 |
| `--out` | Yes | - | 결과 출력 경로 |

#### 사용 환경 변수

| 변수 | 용도 |
|------|------|
| `CLAUDE_CODE_CMD` | architect role subtask 실행 시 사용 |
| `CODEX_CLI_CMD` | builder role subtask 실행 시 사용 |
| `SIMULATE_AGENTS` | `1` 설정 시 시뮬레이션 모드 |
| `AGENT_MAX_RETRIES` | CLI 호출 최대 재시도 횟수 (기본: `2`) |
| `AGENT_RETRY_SLEEP` | 재시도 대기 시간 초 (기본: `20`) |
| `CLI_TIMEOUT_SECONDS` | CLI 명령 타임아웃 초 (기본: `300`) |

#### 출력 형식

```json
{
  "agent": "codex",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "subtask": { "...subtask object..." },
  "role": "builder",
  "files_changed": ["agent/schemas/task.schema.json"],
  "commands_executed": [
    {
      "status": "passed",
      "command": "codex --approval-mode full-auto --quiet",
      "return_code": 0,
      "stdout": "...",
      "stderr": ""
    }
  ],
  "failed_tests": [],
  "artifacts": [],
  "cli_output": { "...raw CLI response..." },
  "open_questions": []
}
```

`status` 값:
- `"done"` -- 구현 성공
- `"failed"` -- CLI가 비정상 종료
- `"blocked"` -- CLI 출력을 파싱할 수 없음 (비 시뮬레이션 모드)

#### Subtask 검색 순서

1. `--dispatch` 파일의 `subtasks` 배열에서 `subtask_id` 매칭
2. 미발견 시 `--task` 파일의 `subtasks` 배열에서 `subtask_id` 매칭
3. 둘 다 없으면 에러 (사용 가능한 subtask ID 목록 표시)

#### 실행 예시

```bash
# 시뮬레이션 모드
SIMULATE_AGENTS=1 python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id ci-cd-collab-baseline-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json

# 실제 CLI (builder role -> CODEX_CLI_CMD 사용)
CODEX_CLI_CMD="codex --approval-mode full-auto --quiet" \
  python3 agent/scripts/orchestrate.py run-implement \
  --task agent/tasks/example.task.json \
  --dispatch agent/results/dispatch_demo.json \
  --subtask-id ci-cd-collab-baseline-S01 \
  --work-id demo \
  --out agent/results/implement_demo_S01.json
```

---

### 5. merge-results

여러 subtask의 implementation 결과를 하나의 통합 리포트로 병합합니다. File lock을 사용하여 동시 접근을 방지합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--work-id` | Yes | - | 작업 식별자 |
| `--kind` | Yes | - | 결과 종류 (예: `implement`) |
| `--input` | Yes | - | 입력 파일 경로 (glob 패턴 지원, 예: `results/implement_demo_*.json`) |
| `--out` | Yes | - | 병합 결과 출력 경로 |
| `--dispatch` | No | `""` | dispatch 파일 경로 (미실행 subtask 감지에 사용) |

#### 출력 형식

```json
{
  "agent": "implement",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "done",
  "count": 2,
  "subtask_results": [ "...각 subtask 결과..." ],
  "files_changed": ["file1.py", "file2.json"],
  "commands_executed": [],
  "failed_tests": [],
  "artifacts": [],
  "open_questions": [],
  "expected_subtasks": ["demo-S01", "demo-S02"],
  "missing_subtasks": []
}
```

`status` 결정 로직 (`build_report_status`):

| 하위 결과에 포함된 status | 최종 status |
|--------------------------|-------------|
| `"failed"` 또는 `"skipped"` | `"failed"` |
| `"blocked"` | `"blocked"` |
| `"simulated"` | `"done"` |
| `"passed"` | `"done"` |
| `"ready"` | `"ready"` |

> `"skipped"`는 `"failed"`와 동일하게 처리됩니다. 이것은 의도적인 품질 정책입니다.

#### File Lock 메커니즘

- 출력 파일에 대해 `.lock` 확장자의 락 파일을 생성
- macOS/Linux: `fcntl.flock` (LOCK_EX | LOCK_NB)
- Windows: `msvcrt.locking` (LK_NBLCK)
- 논블로킹 방식으로 이미 잠긴 파일에 대해서는 즉시 에러 반환

#### Dispatch 기반 완전성 검사

`--dispatch`를 지정하면 dispatch 파일의 `subtasks`에 있는 모든 `subtask_id`가 결과에 포함되었는지 검증합니다. 누락된 subtask가 있으면 status를 `"failed"`로 변경합니다.

#### 실행 예시

```bash
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo \
  --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --dispatch agent/results/dispatch_demo.json \
  --out agent/results/implement_demo.json
```

---

### 6. run-verify

설정된 검증 명령어(test, lint 등)를 실행하고 JUnit XML 리포트를 생성합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--work-id` | Yes | - | 작업 식별자 |
| `--platform` | Yes | - | 실행 플랫폼 (예: `macos`, `windows`) |
| `--out` | Yes | - | 검증 결과 출력 경로 |
| `--commands` | No | `""` | 검증 명령어 (직접 지정 시 다른 소스 무시) |

#### 검증 명령어 소스 (우선순위 순)

1. `--commands` 파라미터 (직접 지정)
2. `VERIFY_COMMANDS` 환경 변수
3. `pipeline-config.json`의 `default_verify_commands` 배열
4. 위 모두 없으면 **파이프라인 실패** (status: `"failed"`)

#### VERIFY_COMMANDS 형식

```bash
# JSON 배열 (권장)
export VERIFY_COMMANDS='["pytest -v", "flake8"]'

# 세미콜론 구분
export VERIFY_COMMANDS="pytest -v; flake8"

# 줄바꿈 구분
export VERIFY_COMMANDS="pytest -v
flake8"
```

#### 출력 형식

```json
{
  "agent": "verify",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "platform": "macos",
  "status": "passed",
  "commands": [
    {
      "command": "python3 -m pytest agent/tests/ -v --tb=short",
      "status": "passed",
      "return_code": 0,
      "time_ms": 3200,
      "stdout": "...test output (max 6000 chars)...",
      "stderr": "...(max 3000 chars)..."
    }
  ],
  "failed_tests": [],
  "artifacts": ["agent/results/junit_demo_macos.xml"],
  "open_questions": []
}
```

#### JUnit XML 리포트

검증 실행 시 자동으로 `junit_{work_id}_{platform}.xml` 파일이 출력 디렉토리에 생성됩니다. CI 시스템의 test report 기능과 연동 가능합니다.

#### 실행 예시

```bash
# 환경 변수 사용
VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v"]' \
  python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo \
  --platform macos \
  --out agent/results/verify_demo_macos.json

# 직접 명령어 지정
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo \
  --platform macos \
  --commands '["pytest -v", "flake8"]' \
  --out agent/results/verify_demo_macos.json
```

---

### 7. run-review

Plan, Implement, Verify 결과를 종합하여 go/no-go 판정을 내리는 품질 게이트입니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--work-id` | Yes | - | 작업 식별자 |
| `--plan` | Yes | - | run-plan 결과 파일 경로 |
| `--implement` | Yes | - | merge-results 결과 파일 경로 |
| `--verify` | No | `[]` | run-verify 결과 파일 경로 (여러 개 가능, nargs) |
| `--out` | Yes | - | 리뷰 결과 출력 경로 |

#### Go/No-Go 판정 기준

**모든 조건을 만족해야 `go_no_go = false` (통과):**

| 조건 | 기대값 |
|------|--------|
| Plan status | `"done"` |
| Implementation status | `"done"` |
| 모든 Verify status | `"passed"` |
| 전 단계 open_questions | 0개 |

> `go_no_go`는 boolean이며, `true`는 "차단됨(블로킹)"을, `false`는 "통과(머지 가능)"를 의미합니다.

#### 출력 형식

```json
{
  "agent": "review",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready_for_merge",
  "claude_review": {
    "status": "approved",
    "notes": []
  },
  "codex_review": {
    "status": "implemented",
    "notes": []
  },
  "action_required": [],
  "open_questions": [],
  "go_no_go": false,
  "references": {
    "plan": "agent/results/plan_demo.json",
    "implement": "agent/results/implement_demo.json",
    "verify": ["macos"]
  }
}
```

`status` 값:
- `"ready_for_merge"` -- 모든 품질 게이트 통과
- `"blocked"` -- 하나 이상의 게이트 미통과

#### 실행 예시

```bash
python3 agent/scripts/orchestrate.py run-review \
  --work-id demo \
  --plan agent/results/plan_demo.json \
  --implement agent/results/implement_demo.json \
  --verify agent/results/verify_demo_macos.json agent/results/verify_demo_windows.json \
  --out agent/results/review_demo.json
```

---

### 8. run-retrospect

리뷰 결과를 분석하여 다음 사이클을 위한 개선 계획(next_plan)을 생성합니다.

#### 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|----------|------|--------|------|
| `--work-id` | Yes | - | 작업 식별자 |
| `--review` | Yes | - | run-review 결과 파일 경로 |
| `--out` | Yes | - | 회고 결과 출력 경로 |

#### 출력 형식

```json
{
  "agent": "retrospect",
  "work_id": "demo",
  "generated_at": "2026-02-15T12:00:00Z",
  "checksum": "sha256...",
  "status": "ready",
  "summary": {
    "go_no_go": false,
    "issues_count": 0,
    "next_action_count": 1
  },
  "next_plan": [
    {
      "index": 1,
      "type": "observe",
      "title": "No critical issues; run routine quality tuning on next cycle.",
      "owner": "both",
      "priority": "medium"
    }
  ],
  "evidence": {
    "review_reference": "agent/results/review_demo.json",
    "questions": []
  }
}
```

#### Next Plan 생성 로직

1. `action_required` 항목이 있으면 각각에 대해 `type: "rework"` 액션 생성 (최대 5개)
   - 항목에 `"implementation"` 포함 -> `owner: "codex"`
   - 그 외 -> `owner: "claude"`
   - 모두 `priority: "high"`
2. `action_required`와 `open_questions`가 모두 비어있으면 `type: "observe"` 단일 항목 생성

#### 실행 예시

```bash
python3 agent/scripts/orchestrate.py run-retrospect \
  --work-id demo \
  --review agent/results/review_demo.json \
  --out agent/results/retrospect_demo.json
```

---

## Schema Reference

모든 스키마는 `agent/schemas/` 디렉토리에 위치합니다. `jsonschema` 패키지 설치 시 validate-task에서 자동으로 스키마 검증이 수행됩니다.

| 스키마 파일 | 용도 | 필수 필드 |
|------------|------|-----------|
| `task.schema.json` | 입력 태스크 정의 | `task_id`, `title`, `scope`, `acceptance_criteria`, `risk_level`, `priority`, `subtasks` |
| `cli-envelope.schema.json` | CLI 에이전트 stdout 출력 래퍼 | `status`, `exit_code`, `stdout`, `stderr` |
| `plan-result.schema.json` | run-plan 결과 | `status`, `implementation_contract`, `test_plan`, `open_questions` |
| `implement-result.schema.json` | run-implement 결과 | `status`, `files_changed`, `commands_executed`, `failed_tests`, `artifacts` |
| `review-result.schema.json` | run-review 결과 | `claude_review`, `codex_review`, `action_required`, `go_no_go` |
| `retrospect.schema.json` | run-retrospect 결과 | `status`, `summary`, `next_plan`, `evidence` |

### task.schema.json 상세

태스크 입력 파일의 구조를 정의합니다. `acceptance_criteria`는 두 가지 형식을 지원합니다:

```json
// 문자열 형식 (간단)
"acceptance_criteria": ["Tests pass", "Lint clean"]

// 객체 형식 (머신 검증 가능)
"acceptance_criteria": [
  {
    "id": "AC-S01-1",
    "description": "Schema files are valid JSON",
    "verification": "python3 -c \"import json...\"",
    "type": "automated"
  }
]
```

Subtask의 `role` 필드는 `"architect"` 또는 `"builder"` 중 하나를 사용합니다. 하위 호환을 위해 `owner: "claude"/"codex"` 필드도 지원됩니다.

### cli-envelope.schema.json 상세

CLI 래퍼(claude-wrapper.sh, codex-wrapper.sh)가 stdout으로 출력하는 JSON 엔벨로프입니다. `additionalProperties: false`로 스키마 외 필드를 허용하지 않습니다.

```json
{
  "status": "passed",
  "exit_code": 0,
  "stdout": "{\"result\": {\"files_changed\": [\"app.py\"]}}",
  "stderr": "",
  "result": { "files_changed": ["app.py"] }
}
```

### plan-result.schema.json 상세

`chunks` 배열의 각 항목은 30-90분 구현 단위를 나타내며, 머신 검증 가능한 acceptance_criteria를 포함합니다:

```json
{
  "chunk_id": "task-C01",
  "title": "Setup project structure",
  "estimated_minutes": 60,
  "role": "builder",
  "depends_on": [],
  "acceptance_criteria": [
    {
      "id": "AC-001",
      "description": "Project directories exist",
      "verify_command": "test -d src && test -d tests",
      "verify_pattern": "",
      "category": "structural"
    }
  ]
}
```

`category` 값: `"functional"`, `"structural"`, `"quality"`, `"integration"`

---

## Troubleshooting Guide

### "CLI command not configured"

**증상**: `RuntimeError: claude CLI command not configured` 또는 `codex CLI command not configured`

**원인**: `CLAUDE_CODE_CMD` 또는 `CODEX_CLI_CMD` 환경 변수가 설정되지 않은 상태에서 `SIMULATE_AGENTS`도 비활성.

**해결 방법**:

```bash
# 방법 1: CLI 경로 설정
export CLAUDE_CODE_CMD="claude --print"
export CODEX_CLI_CMD="codex --approval-mode full-auto --quiet"

# 방법 2: 시뮬레이션 모드 사용 (CLI 없이 테스트)
export SIMULATE_AGENTS=1
```

---

### "Task validation failed"

**증상**: validate-task가 exit code 2를 반환하고 `validation_errors`에 오류 목록이 있음.

**원인**: 태스크 JSON이 `task.schema.json`의 필수 필드나 형식 조건을 만족하지 않음.

**해결 방법**:

```bash
# 1. 검증 결과 확인
python3 agent/scripts/orchestrate.py validate-task \
  --task your_task.json \
  --out /tmp/validation.json --verbose

# 2. 결과 파일에서 오류 확인
python3 -c "import json; print(json.dumps(json.load(open('/tmp/validation.json'))['validation_errors'], indent=2))"

# 3. JSON 문법 확인
python3 -m json.tool your_task.json
```

**자주 발생하는 오류**:

| validation_error 메시지 | 원인 | 수정 방법 |
|------------------------|------|-----------|
| `missing task_id` | task_id 필드 누락 | `"task_id": "my-task-001"` 추가 |
| `missing title` | title 필드 비어있음 | 의미있는 제목 작성 |
| `acceptance_criteria must be a non-empty array` | acceptance_criteria 누락/비어있음 | 최소 1개 항목 추가 |
| `subtasks should be an array` | subtasks가 배열이 아닌 객체 | `[...]` 배열 형태로 변환 |
| `jsonschema package not installed` | jsonschema 미설치 | `pip install jsonschema` |

---

### "Verification skipped"

**증상**: run-verify가 exit code 1을 반환하고 `status: "failed"`이며, `open_questions`에 "VERIFY_COMMANDS not configured" 메시지가 있음.

**원인**: 검증 명령어가 어떤 소스에서도 설정되지 않음.

**해결 방법**:

```bash
# 방법 1: 환경 변수 설정 (권장)
export VERIFY_COMMANDS='["python3 -m pytest agent/tests/ -v", "flake8"]'

# 방법 2: --commands 직접 지정
python3 agent/scripts/orchestrate.py run-verify \
  --work-id demo --platform macos \
  --commands '["pytest -v"]' \
  --out agent/results/verify_demo.json

# 방법 3: pipeline-config.json에 기본값 설정
# "default_verify_commands": ["pytest -v", "flake8"]
```

> 파이프라인 품질 정책상 `VERIFY_COMMANDS` 미설정은 즉시 실패 처리됩니다. "skipped" 상태는 존재하지 않으며, 검증이 불가능한 경우 반드시 `"failed"`로 처리됩니다.

---

### "Merge lock failed"

**증상**: merge-results가 `Unable to acquire merge lock` 에러와 함께 exit code 1을 반환.

**원인**: 다른 파이프라인 프로세스가 동일한 출력 파일에 쓰기 작업 중이거나, 이전 실행의 stale lock 파일이 남아있음.

**해결 방법**:

```bash
# 1. 다른 프로세스 확인
ps aux | grep orchestrate

# 2. Stale lock 파일 확인 및 제거
ls -la agent/results/*.lock
rm agent/results/implement_demo.json.lock  # stale lock 제거

# 3. 다시 실행
python3 agent/scripts/orchestrate.py merge-results \
  --work-id demo --kind implement \
  --input "agent/results/implement_demo_*.json" \
  --out agent/results/implement_demo.json
```

---

### "Command timed out"

**증상**: `Command timed out after Ns` 에러. CLI 명령 또는 검증 명령이 타임아웃 시간을 초과.

**원인**: CLI_TIMEOUT_SECONDS(기본 300초)보다 긴 실행 시간의 명령.

**해결 방법**:

```bash
# 타임아웃 늘리기 (초 단위)
export CLI_TIMEOUT_SECONDS=600  # 10분

# 특정 명령만 타임아웃 조정이 필요한 경우
# 검증 명령 자체에 타임아웃 옵션 추가
export VERIFY_COMMANDS='["timeout 120 pytest -v --timeout=60"]'
```

---

### "Rate limit exceeded"

**증상**: CLI 에이전트가 rate limit 에러를 반환하며 재시도에도 실패.

**원인**: Claude 또는 Codex API의 호출 빈도 제한에 도달.

**해결 방법**:

```bash
# 재시도 횟수 늘리기
export AGENT_MAX_RETRIES=5

# 재시도 대기 시간 늘리기 (초)
export AGENT_RETRY_SLEEP=60

# pipeline-config.json에서 기본값 변경
# "defaults": { "rate_limit_seconds": 5, "retry_count": 3 }
```

> `run_agent_command`는 실패 시 최대 `AGENT_MAX_RETRIES`회 재시도하며, 각 재시도 사이에 `AGENT_RETRY_SLEEP`초 대기합니다. 성공(`return_code == 0`) 시 즉시 반환됩니다.

---

### 추가 팁

| 상황 | 진단 방법 |
|------|-----------|
| 어떤 단계에서 실패하는지 모름 | `--verbose` 옵션 추가하여 DEBUG 로그 확인 |
| CLI 출력을 직접 확인하고 싶음 | 결과 JSON의 `cli_output` 필드에 raw 출력 포함 |
| 파이프라인 전체 테스트 | `SIMULATE_AGENTS=1 ./agent/scripts/pipeline-runner.sh --task ... --work-id test` |
| subtask ID를 모름 | validate-task 또는 split-task 결과의 `subtasks[].subtask_id` 확인 |
| 파이프라인 중간부터 재실행 | 해당 action을 직접 호출하고 이전 단계 결과 경로를 지정 |

---

## Configuration Reference

### pipeline-config.json

파이프라인의 동작을 제어하는 중앙 설정 파일입니다. 위치: `agent/pipeline-config.json`

```json
{
  "pipeline_mode": "local-only",
  "supported_modes": ["local-only", "orchestrator-centralized"],
  "defaults": { ... },
  "roles": { ... },
  "default_verify_commands": [ ... ]
}
```

#### 전체 옵션 목록

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `pipeline_mode` | string | `"local-only"` | 파이프라인 실행 모드. `"local-only"`: 단일 머신 실행, `"orchestrator-centralized"`: 중앙 오케스트레이터 사용 |
| `supported_modes` | string[] | `["local-only", "orchestrator-centralized"]` | 지원하는 실행 모드 목록 |

#### defaults 섹션

| 키 | 타입 | 기본값 | 환경 변수 오버라이드 | 설명 |
|----|------|--------|---------------------|------|
| `max_retries` | int | `2` | `AGENT_MAX_RETRIES` | CLI 호출 최대 재시도 횟수 |
| `retry_sleep_seconds` | int | `20` | `AGENT_RETRY_SLEEP` | 재시도 간 대기 시간 (초) |
| `cli_timeout_seconds` | int | `300` | `CLI_TIMEOUT_SECONDS` | CLI 명령 타임아웃 (초) |
| `rate_limit_seconds` | int | `2` | `AGENT_RATE_LIMIT` | API 호출 간 최소 간격 (초) |
| `retry_count` | int | `2` | - | max_retries의 별칭 |
| `log_level` | string | `"INFO"` | - | 로깅 레벨 (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`) |
| `result_retention_days` | int | `30` | - | 결과 파일 보존 기간 (일) |
| `results_dir_pattern` | string | `"agent/results/{os_prefix}/{work_id}"` | - | 결과 디렉토리 경로 패턴 |

#### roles 섹션

| 역할 | 설명 | 환경 변수 |
|------|------|-----------|
| `architect` | 계획, 설계, 리뷰 -- 주로 Claude Code CLI | `CLAUDE_CODE_CMD` |
| `builder` | 구현, 실행, 테스트 -- 주로 Codex CLI | `CODEX_CLI_CMD` |

#### default_verify_commands

VERIFY_COMMANDS 환경 변수 미설정 시 사용되는 기본 검증 명령어 배열입니다:

```json
"default_verify_commands": [
  "python3 -m pytest agent/tests/ -v --tb=short",
  "python3 -c \"import json,pathlib; [json.loads(p.read_text()) for p in pathlib.Path('agent/schemas').glob('*.json')]\""
]
```

### 환경 변수 전체 목록

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `CLAUDE_CODE_CMD` | 조건부* | - | Claude Code CLI 실행 명령어 |
| `CODEX_CLI_CMD` | 조건부* | - | Codex CLI 실행 명령어 |
| `SIMULATE_AGENTS` | No | `"0"` | `"1"` 또는 `"true"` 시 시뮬레이션 모드 활성화 |
| `VERIFY_COMMANDS` | No | pipeline-config.json 참조 | 검증 명령어 (JSON 배열, 세미콜론, 줄바꿈 구분 지원) |
| `AGENT_MAX_RETRIES` | No | `"2"` | CLI 호출 최대 재시도 횟수 |
| `AGENT_RETRY_SLEEP` | No | `"20"` | 재시도 대기 시간 (초) |
| `CLI_TIMEOUT_SECONDS` | No | `"300"` | CLI 명령 타임아웃 (초) |

> *`SIMULATE_AGENTS=1`이 아닌 경우, architect subtask 실행 시 `CLAUDE_CODE_CMD`가, builder subtask 실행 시 `CODEX_CLI_CMD`가 각각 필수입니다.

### pipeline-runner.sh 옵션

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--task` | Yes | - | 태스크 JSON 파일 경로 |
| `--work-id` | No | SHA256(task file)[:12] | 작업 식별자 (미지정 시 태스크 파일 해시에서 자동 생성) |
| `--results-dir` | No | `agent/results` | 결과 출력 디렉토리 |
| `--mode` | No | `full` | 실행 모드: `full` (전체 8단계) 또는 `implement-only` (validate~merge 5단계만) |
