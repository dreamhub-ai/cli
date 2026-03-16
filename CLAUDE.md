# dreamhubcli

Python CLI tool — unified command-line interface for all Dreamhub APIs.

- Single `dh` command for all CRM operations
- Framework: Typer + httpx + Rich
- Auth: PAT tokens + OAuth2 PKCE browser flow, with `x-tenant-id` header
- Config stored at `~/.dreamhub/config.toml`

## Local Development

```shell
poetry install
poetry run pytest            # unit tests
poetry run dh --help         # verify CLI works
```

## Architecture

- **`dreamhubcli/main.py`** — Typer app, registers all command groups
- **`dreamhubcli/commands/_crud.py`** — Factory that generates list/get/create/update/delete/filter for entity command groups
- **`dreamhubcli/commands/`** — One module per command group (auth, search, reporting, etc.)
- **`dreamhubcli/client.py`** — httpx-based API client with auth header injection
- **`dreamhubcli/config.py`** — TOML config loader/saver (Pydantic model)
- **`dreamhubcli/auth.py`** — Login/logout helpers
- **`dreamhubcli/auth_callback.py`** — OAuth2 PKCE flow with localhost callback server
- **`dreamhubcli/output.py`** — Rich console formatting, `print_error` writes to stderr
- **`dreamhubcli/errors.py`** — HTTP error handling with user-friendly messages

## Command Groups

13 groups: auth, companies, deals, leads, people, users, settings, history, tasks, search, reporting, enrichment (dev), access (dev)

CRUD entities use the shared factory — add new ones by calling `build_crud_app()` in a new module.

## Test Structure

- `tests/unit/` — fast tests with mocked HTTP (respx), no network
- `tests/e2e/` — staging API tests, marked with `@pytest.mark.e2e`, skipped by default
- Run e2e: `DH_E2E_TOKEN=xxx DH_E2E_TENANT_ID=yyy poetry run pytest -m e2e -v`

## Conventions

- `--json` flag on every list/get command for machine-readable output
- Every command has `Examples:` in its `--help` epilog
- Error messages go to stderr via `print_error()`
- Dev-only commands gated behind `is_dev_environment()` in `config.py`
