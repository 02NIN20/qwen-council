# Multi-Agent Council — MCP Server

Connect the Agent Society to any MCP-compatible client in 3 steps.

## Setup

### 1. Install

```bash
git clone https://github.com/02NIN20/multiagent-council.git
cd multiagent-council
pip install -r backend/requirements.txt
```

### 2. Configure

Copy and edit `.env.example`:

```bash
cp .env.example .env
```

For **local use with Ollama** (no API key needed):
```env
llm_provider=ollama
llm_model=qwen2.5-coder:7b
llm_base_url=http://localhost:11434/v1
```

For **Qwen Cloud** (requires API key):
```env
llm_provider=qwen
llm_api_key=sk-your-key
llm_model=qwen-plus-2025-07-28
```

For **OpenAI**:
```env
llm_provider=openai
llm_api_key=sk-your-key
llm_model=gpt-4o
```

### 3. Run

```bash
bash run_mcp.sh
```

The server starts in **stdio mode** — it listens on stdin/stdout
for MCP messages from the client.

## Client Configuration

### OpenCode

Add to `~/.config/opencode/opencode.jsonc`:

```json
{
  "mcp": {
    "multiagent-council": {
      "type": "local",
      "command": ["bash", "/path/to/multiagent-council/run_mcp.sh"]
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "multiagent-council": {
      "command": "bash",
      "args": ["/path/to/multiagent-council/run_mcp.sh"]
    }
  }
}
```

## Tools

| Tool | Description |
|:-----|:------------|
| `review_code(code, instruction, mode)` | Full multi-agent code review (6 agents, 3 rounds) |
| `chat(message, images?)` | Ask the 6-agent society any question. Supports images via vision pipeline |
| `analyze_file(filename, content, question)` | Analyze code or text files |
| `generate_code(specification, language)` | Generate code from spec |
| `implement_fix(code, issue)` | Fix code issues |

## Run Anywhere

The server is a standalone Python script — no database, no API server,
no cloud dependencies required (when using Ollama).
