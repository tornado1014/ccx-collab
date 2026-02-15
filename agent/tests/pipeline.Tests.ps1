# Pester smoke tests for the CI/CD pipeline (Windows)
# Run with: Invoke-Pester -Path agent/tests/pipeline.Tests.ps1

Describe "Pipeline Scripts Exist" {
    It "pipeline-runner.ps1 exists" {
        Test-Path "agent/scripts/pipeline-runner.ps1" | Should -BeTrue
    }

    It "claude-wrapper.ps1 exists" {
        Test-Path "agent/scripts/claude-wrapper.ps1" | Should -BeTrue
    }

    It "codex-wrapper.ps1 exists" {
        Test-Path "agent/scripts/codex-wrapper.ps1" | Should -BeTrue
    }

    It "orchestrate.py exists" {
        Test-Path "agent/scripts/orchestrate.py" | Should -BeTrue
    }
}

Describe "Pipeline Runner Structure" {
    BeforeAll {
        $content = Get-Content "agent/scripts/pipeline-runner.ps1" -Raw
    }

    It "has validation stage" {
        $content | Should -Match "validate"
    }

    It "has planning stage" {
        $content | Should -Match "plan"
    }

    It "has split stage" {
        $content | Should -Match "split"
    }

    It "has implement stage" {
        $content | Should -Match "implement"
    }

    It "has merge stage" {
        $content | Should -Match "merge"
    }

    It "has verify stage" {
        $content | Should -Match "verify"
    }

    It "has review stage" {
        $content | Should -Match "review"
    }
}

Describe "CLI Wrapper Envelope Contract" {
    BeforeAll {
        $claudeContent = Get-Content "agent/scripts/claude-wrapper.ps1" -Raw
        $codexContent = Get-Content "agent/scripts/codex-wrapper.ps1" -Raw
    }

    It "claude-wrapper reads stdin JSON" {
        $claudeContent | Should -Match "ReadToEnd|ConvertFrom-Json"
    }

    It "claude-wrapper outputs JSON envelope" {
        $claudeContent | Should -Match "ConvertTo-Json"
    }

    It "claude-wrapper handles CLAUDECODE env var" {
        $claudeContent | Should -Match "CLAUDECODE"
    }

    It "codex-wrapper reads stdin JSON" {
        $codexContent | Should -Match "ReadToEnd|ConvertFrom-Json"
    }

    It "codex-wrapper outputs JSON envelope" {
        $codexContent | Should -Match "ConvertTo-Json"
    }

    It "codex-wrapper handles CLAUDECODE env var" {
        $codexContent | Should -Match "CLAUDECODE"
    }
}

Describe "Orchestrate.py Commands" {
    It "orchestrate.py responds to --help" {
        $result = python3 agent/scripts/orchestrate.py --help 2>&1
        $LASTEXITCODE | Should -Be 0
    }

    It "orchestrate.py has validate-task command" {
        $result = python3 agent/scripts/orchestrate.py validate-task --help 2>&1
        $LASTEXITCODE | Should -Be 0
    }

    It "orchestrate.py has run-verify command" {
        $result = python3 agent/scripts/orchestrate.py run-verify --help 2>&1
        $LASTEXITCODE | Should -Be 0
    }
}

Describe "Pipeline Configuration" {
    BeforeAll {
        $config = Get-Content "agent/pipeline-config.json" -Raw | ConvertFrom-Json
    }

    It "has pipeline_mode" {
        $config.pipeline_mode | Should -Not -BeNullOrEmpty
    }

    It "has roles defined" {
        $config.roles | Should -Not -BeNullOrEmpty
    }

    It "has default_verify_commands" {
        $config.default_verify_commands | Should -Not -BeNullOrEmpty
    }
}
