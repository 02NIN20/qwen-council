# Multi-Agent Council — MCP Server Setup

Connect the Agent Society to any MCP-compatible client:
- **OpenCode**
- **Claude Desktop**
- **Cursor**
- **Any MCP client**

## Quick Start (OpenCode)

### 1. Prerequisites

```bash
# Install dependencies
pip install mcp httpx openai

# Clone the repo
git clone https://github.com/02NIN20/multiagent-council.git
cd multiagent-council
```

### 2. Add to OpenCode config

Add to `~/.config/opencode/opencode.jsonc`:

```json
{
  "mcp": {
    "multiagent-council": {
      "type": "local",
      "command": ["bash", "/ABSOLUTE/PATH/to/multiagent-council/run_mcp.sh"],
      "enabled": true
    }
  }
}
```

Replace `/ABSOLUTE/PATH/to/multiagent-council/` with the actual path.

### 3. Configure the API URL

By default, `run_mcp.sh` connects to `http://localhost:8000`.
To use a remote instance, set the environment variable:

```bash
export QWEN_COUNCIL_API_URL=http://your-server:8000
```

### 4. Restart OpenCode

Close and reopen OpenCode. The `multiagent-council` MCP server should appear.

## Available Tools

| Tool | Description | Use Case |
|:-----|:------------|:---------|
| `chat` | Ask the Agent Society | Design advice, brainstorming, architecture |
| `analyze_file` | Analyze a code file | Code review, bug finding |
| `review_code` | Multi-agent code review (3 rounds) | Deep code analysis |
| `generate_code` | Generate code from spec | Write new code |
| `implement_fix` | Fix code issues | Bug fixing |
| `list_sessions` | List past sessions | History |
| `get_session` | Get session details | Review past work |

## Tips

- **`chat`** is fastest — use for design questions and brainstorming
- **`analyze_file`** works best for files < 3000 chars (direct LLM for larger)
- **`review_code`** use `mode: "light"` for faster results, `mode: "full"` for thorough
- Set `QWEN_COUNCIL_API_URL` to your own deployed instance if needed
