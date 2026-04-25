# Dreamhub CLI

Command-line interface for [Dreamhub](https://www.dreamhub.ai/) — the AI-native CRM for B2B SaaS.

Manage companies, deals, leads, people, and more directly from your terminal.

## Install

One command — handles everything (Python, pipx, CLI):

**macOS / Linux:**
```shell
curl -fsSL https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.sh | bash
```

**Windows** (PowerShell):
```powershell
irm https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.ps1 | iex
```

<details>
<summary>Manual install (if you already have pipx)</summary>

```shell
pipx install git+https://github.com/dreamhub-ai/cli.git
```

Or with pip:

```shell
pip install git+https://github.com/dreamhub-ai/cli.git
```
</details>

## Login

```shell
# Opens your browser for secure login
dh auth login

# Or use a personal access token
dh auth login --token pat_xxx --tenant-id my-tenant
```

## Usage

```shell
# List and filter records
dh companies list
dh deals list --page 2 --page-size 50
dh companies filter name contains_nocase Acme
dh deals filter status eq 1 and name contains Dreamhub

# Get a single record
dh deals get d-acm-1a2b3c4d
dh companies get c-acm-5e6f7a8b --json

# Create and update
dh leads create '{"firstName": "Jane", "lastName": "Doe"}'
dh companies update c-acm-5e6f7a8b '{"industry": "SaaS"}'

# Search across all entities
dh search "Acme Corp"
dh search "Acme" --type companies

# Reports and settings
dh reporting list
dh reporting get kpis --json
dh settings list
dh settings get account_currency

# Activity history
dh history
```

Most data commands support `--json` for machine-readable output, and all commands support `--help` for usage examples.

## Claude Desktop Integration

Use Dreamhub as an MCP tool provider in Claude Desktop — lets Claude read and manage your CRM data directly.

```shell
# Auto-configure Claude Desktop
dh mcp install

# Preview the config without writing
dh mcp install --dry-run

# Remove the integration
dh mcp uninstall
```

Restart Claude Desktop after install/uninstall to apply changes.

Once connected, Claude can list, search, create, and update companies, deals, leads, people, tasks, activities, and more through natural conversation.

## Shell Completion

Enable tab completion for your shell:

```shell
dh --install-completion
```

Supports bash, zsh, fish, and PowerShell.

## Configuration

Credentials and settings are stored locally at `~/.dreamhub/config.toml`.

```shell
# Check current auth status
dh auth status

# Log out (clears stored credentials)
dh auth logout
```

## Contributing

```shell
git clone https://github.com/dreamhub-ai/cli.git
cd cli
poetry install
poetry run pytest
```

## License

Apache 2.0. See [LICENSE](LICENSE) for details.
