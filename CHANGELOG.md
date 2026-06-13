# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Open-sourced as public template repository.
- Docker support (`Dockerfile`, `docker-compose.yml`).
- GitHub community files: issue templates, PR template, Dependabot, CodeQL.
- Developer experience tooling: `ruff`, `pre-commit`, `pyproject.toml`, `.editorconfig`.
- OSS standard files: `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.

### Changed

- De-branded all client-specific references to generic `YOUR_COMPANY` placeholders.
- Renamed prompt docs to `vapi-system-prompt.md` (Persona A) and `vapi-system-prompt-persona-b.md` (Persona B).
- Rewrote `README.md` as a complete project guide.

### Removed

- Internal planning documents and client-specific assets.

## [1.0.0] - 2026-02-15

### Added

- Phase 1 backend (FastAPI + queue + webhook + lead classification).
- Phase 2 frontend dashboard (upload, start campaign, live status polling).
- Vapi outbound call integration and Twilio WhatsApp integration paths.
- Test coverage and runbooks for team handoff.
- CI pipeline via GitHub Actions (`backend tests`, `frontend tests + build`, `security checks`).

### Included Components

- Lead ingestion API (`/upload`).
- Lead listing API (`/leads`).
- Campaign queue trigger (`/start-campaign`).
- Vapi webhook receiver (`/webhook/vapi`).
- Manager status endpoint (`/manager-status`).
- Campaign dashboard UI with CSV upload and live lead status table.
- Trial mode warning banner.
- Helper scripts: `scripts/start-demo.ps1`, `scripts/stop-demo.ps1`.
- Vapi debug scripts for troubleshooting.

### Verification Status

- Backend tests: pass.
- Frontend tests: pass.
- Frontend production build: pass.
- Runtime smoke checks: pass.

[unreleased]: https://github.com/N1KH1LT0X1N/Parmar/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/N1KH1LT0X1N/Parmar/releases/tag/v1.0.0
