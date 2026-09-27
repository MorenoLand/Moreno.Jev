# Structured code review with Jev

Moreno.Jev exposes TypeSafe Jev through a local Model Context Protocol (MCP) server. It works with Codex and other MCP-capable clients, including Pi through its MCP adapter.

The server provides four tools:

- `jev_review_code` asks Jev for a structured bug triage, category, severity, and human-review signal.
- `jev_review_diff` checks a proposed change for regressions using the same structured review.
- `jev_check_hypothesis` estimates whether a debugging hypothesis fits the supplied code and symptom.
- `jev_evaluate` sends custom typed Choice, Score, and Noul questions.

Jev returns structured decisions, not explanations or code patches. The connected coding agent should verify the results and explain any findings.

## Requirements

- Python 3.10 or newer
- uv, or pip and Python's built-in virtual-environment support
- A TypeSafe API key available to the MCP process as `TYPESAFE_API_KEY`

## Install

Clone the repository, then install the locked dependencies:

```sh
git clone https://github.com/MorenoLand/Moreno.Jev.git
cd Moreno.Jev
uv sync --locked
```

The project creates its virtual environment in `.venv`. To use pip instead, create a virtual environment with `python -m venv .venv`, activate it for your platform, and run `python -m pip install -e .`.

Set `TYPESAFE_API_KEY` in the environment used to launch Codex, Pi, or another MCP client. Do not put the key in this repository or in the MCP configuration. Restart the client after changing a persistent environment variable.

## Codex

Add a user-level entry to `~/.codex/config.toml`. Replace the paths with the absolute paths to this clone.

Windows:

```toml
[mcp_servers.moreno-jev]
command = "C:/path/to/Moreno.Jev/.venv/Scripts/python.exe"
args = ["-u", "-m", "jev_mcp"]
cwd = "C:/path/to/Moreno.Jev"
env_vars = ["TYPESAFE_API_KEY"]
```

macOS or Linux:

```toml
[mcp_servers.moreno-jev]
command = "/path/to/Moreno.Jev/.venv/bin/python"
args = ["-u", "-m", "jev_mcp"]
cwd = "/path/to/Moreno.Jev"
env_vars = ["TYPESAFE_API_KEY"]
```

The `env_vars` entry forwards the named variable from Codex's environment; it does not store the key in TOML. Restart Codex after editing the configuration.

To make the skill available across repositories, copy `.agents/skills/jev-review` from this checkout into `~/.agents/skills/jev-review` (Windows: `%USERPROFILE%\.agents\skills\jev-review`). Codex and Pi both discover Agent Skills from this user location; Pi can also use the checked-in project skill and invoke it with `/skill:jev-review`.

Suggested AGENTS.md instruction:

```text
When I ask for Jev review or invoke the Jev skill, use the moreno-jev MCP tools on only the relevant code, diff, or debugging hypothesis. Report Jev's structured answers and probabilities, then independently verify flagged issues against the repository and give me evidence and a concrete next step. Never include credentials or unrelated private data in the submitted state.
```

Then invoke it with `$jev-review` or ask for a Jev review.

## Pi

Pi uses MCP through the `pi-mcp-adapter` package. Install it with `pi install npm:pi-mcp-adapter`, then restart Pi. Add the following to the project `.mcp.json` or user-global `~/.config/mcp/mcp.json`, replacing the paths for your OS:

```json
{
  "mcpServers": {
    "moreno-jev": {
      "command": "/path/to/Moreno.Jev/.venv/bin/python",
      "args": ["-u", "-m", "jev_mcp"],
      "cwd": "/path/to/Moreno.Jev",
      "inheritEnv": false,
      "env": {
        "TYPESAFE_API_KEY": "${TYPESAFE_API_KEY}"
      }
    }
  }
}
```

On Windows, use a command such as `C:/path/to/Moreno.Jev/.venv/Scripts/python.exe`. The `inheritEnv` and `env` fields use pi-mcp-adapter's environment handling so the server receives only the explicitly forwarded key.

Pi also discovers this skill from the same `.agents/skills` path. The adapter exposes MCP through its `mcp` gateway. If Jev tools are not direct tools in your Pi session, search for `jev_review_diff` or `jev_check_hypothesis` with `mcp({ search: "jev_review_diff" })`, then call the returned tool name. Use `/skill:jev-review` to load the workflow.

## Other MCP clients

Configure a stdio server with the virtual-environment Python executable, arguments `["-u", "-m", "jev_mcp"]`, and the repository as its working directory. Forward `TYPESAFE_API_KEY` through that client's environment mechanism; do not copy the key into shared configuration.

## Data handling

The server does not read repository files, persist prompts, or log request bodies or credentials. A tool call sends its supplied state and questions to TypeSafe's Jev API. Use the skill to keep submissions limited to the material relevant to the review.
