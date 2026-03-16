# Contributing to dreamhubcli

Thanks for your interest in contributing to the Dreamhub CLI! This tool is built by [Dreamhub](https://dreamhub.ai) and we welcome community contributions.

## Before You Start

- **Open an issue first.** Before writing code, open a GitHub issue describing what you want to change. This helps avoid duplicate work and ensures alignment.
- **Only pick up issues labeled `help wanted` or `good first issue`.** These are explicitly scoped for community contributors.

## Development Workflow

1. Fork this repository and clone your fork.
2. Create a feature branch from `main`:
   ```bash
   git checkout -b my-feature
   ```
3. Install dependencies and run tests:
   ```bash
   poetry install
   poetry run pytest
   ```
4. Make your changes, ensuring tests pass.
5. Push your branch and open a pull request against `main`.

## Pull Request Guidelines

- Reference the GitHub issue your PR addresses (e.g., `Fixes #123`).
- Keep PRs focused — one logical change per PR.
- Ensure all tests pass before requesting review.
- Do not commit secrets, credentials, or API keys.

## License

By submitting a pull request, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
