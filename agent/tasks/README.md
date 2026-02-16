# Example Task Gallery

Example task definitions for the cc-collab pipeline. Use these as templates when creating your own tasks.

## Available Examples

| File | Complexity | Roles | Description |
|------|-----------|-------|-------------|
| `example.task.json` | Medium | builder | Baseline CI/CD pipeline task |
| `simple-feature.task.json` | Low | builder | Single subtask feature addition |
| `multi-stage-refactor.task.json` | High | architect + builder | Multi-subtask refactoring |
| `testing-infrastructure.task.json` | Low | builder | Test framework setup |
| `documentation-update.task.json` | Low | architect | Documentation creation |

## Creating Your Own Task

1. Copy the closest example to your needs
2. Update `task_id`, `title`, and `scope`
3. Define acceptance criteria with verification commands
4. Add subtasks with appropriate roles:
   - `architect` -- planning, documentation, design (uses Claude Code)
   - `builder` -- implementation, coding (uses Codex CLI)
5. Run validation: `cc-collab validate --task your-task.json`

## Task Schema

All tasks must conform to `agent/schemas/task.schema.json`. Key fields:

- `task_id` (required): Unique identifier
- `title` (required): Human-readable title
- `scope` (required): Implementation scope description
- `risk_level`: "low" | "medium" | "high"
- `priority`: "low" | "medium" | "high" | "critical"
- `acceptance_criteria`: Array of verification conditions
- `subtasks`: Array of work units with roles

## Subtask Fields

Each subtask supports the following fields:

- `subtask_id`: Unique identifier (convention: `{task_id}-S{nn}`)
- `title` (required): Human-readable subtask title
- `role`: `"architect"` or `"builder"`
- `platform`: Target platform(s) -- `"both"`, `"mac"`, or `"windows"`
- `estimated_minutes`: Expected implementation time (30-90 minutes)
- `depends_on`: Array of subtask IDs that must complete first
- `files_affected`: Array of file paths this subtask will create or modify
- `acceptance_criteria` (required): Array of verification conditions

## Acceptance Criteria Format

Each acceptance criterion is an object with these fields:

```json
{
  "id": "AC-S01-1",
  "description": "Human-readable description of what is verified",
  "verification": "shell-command-that-exits-0-on-success",
  "type": "automated"
}
```

The `id` field follows the pattern `AC-S{subtask_number}-{criterion_number}`. Use `AC-S00-N` for top-level criteria that apply to the entire task.

## Verification Commands

Each acceptance criterion should include a `verification` command that:
- Returns exit code 0 on success
- Returns non-zero exit code on failure
- Can be run independently
- Produces meaningful error messages on failure

### Common Verification Patterns

**Check file existence:**
```bash
test -s path/to/file.py
```

**Check Python imports:**
```bash
python3 -c "from mymodule import MyClass"
```

**Run specific tests:**
```bash
pytest tests/test_feature.py -v
```

**Assert content in files:**
```bash
grep -q 'expected_content' path/to/file.py
```

**Complex Python assertions:**
```bash
python3 -c "import pathlib; content = pathlib.Path('file.py').read_text(); assert 'class MyRepo' in content"
```

## Role Guidelines

| Role | Agent | Best For |
|------|-------|----------|
| `architect` | Claude Code | Design, planning, documentation, code review, interface definitions |
| `builder` | Codex CLI | Implementation, coding, test writing, refactoring |

A typical complex task uses `architect` for the first subtask (design/planning) and `builder` for subsequent implementation subtasks.
