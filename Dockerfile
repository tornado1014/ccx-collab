FROM python:3.12-slim

LABEL maintainer="earendel"
LABEL description="CLI tool for Claude Code + Codex CLI collaboration pipeline"
LABEL version="0.1.0"

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY pyproject.toml .
COPY LICENSE .
COPY README.md .
COPY ccx_collab/ ccx_collab/
COPY agent/ agent/

# Install the package (editable so ccx_collab source stays at /app)
RUN pip install --no-cache-dir -e .

# Default environment variables (can be overridden at runtime)
ENV SIMULATE_AGENTS="1"
ENV CLAUDE_CODE_CMD="claude"
ENV CODEX_CLI_CMD="codex"
ENV VERIFY_COMMANDS="true"

ENTRYPOINT ["ccx-collab"]
CMD ["--help"]
