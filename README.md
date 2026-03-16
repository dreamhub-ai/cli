# Dreamhub CLI

Command-line interface for [Dreamhub](https://www.dreamhub.ai/) — the AI-native CRM for B2B SaaS.

Manage companies, deals, leads, people, and more directly from your terminal.

## Install

```shell
pipx install git+https://github.com/dreamhub-ai/cli.git
```

Or with pip:

```shell
pip install git+https://github.com/dreamhub-ai/cli.git
```

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
dh deals get D-AB-1234
dh companies get CO-AB-5678 --json

# Create and update
dh leads create '{"firstName": "Jane", "lastName": "Doe"}'
dh companies update CO-AB-1 '{"industry": "SaaS"}'

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

# Switch tenant
dh auth set-tenant other-tenant-id

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
