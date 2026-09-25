# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within RedOps Eval, please send an email to the maintainers. All security vulnerabilities will be promptly addressed.

Please do **not** report security vulnerabilities through public GitHub issues.

### What to include

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Suggested fix (if any)

### Response timeline

- Acknowledgment within 48 hours
- Initial assessment within 1 week
- Fix or mitigation within 30 days for critical issues

## Security Measures

- JWT-based authentication with configurable token expiry
- Rate limiting middleware (per-IP sliding window, configurable per route)
- Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, Permissions-Policy)
- Input validation via Pydantic models
- SQL injection prevention via SQLAlchemy ORM
- CORS configuration (origin-restricted)
- Idempotency-key support on run creation (safe CI/CD retries)
- Dependency vulnerability scanning via pip-audit and npm audit
- Container image scanning via Trivy in CI/CD
- Secrets scanning via Gitleaks in CI and pre-commit

## Security Audit Notes

### Input sanitization

All HTTP request bodies and query parameters are parsed and validated
through Pydantic models before reaching application logic. Field types,
constraints, and enumerations are enforced, and values that fail validation
are rejected with structured errors. SQL injection is mitigated by using
SQLAlchemy's ORM/query builder (parameterized statements) rather than string
interpolation. Prompt and dataset content is treated as opaque user data and
is never interpreted as code.

### XSS

Client-side, the Next.js/React frontend escapes rendered values by default,
and no `dangerouslySetInnerHTML` is used on user-supplied data. Server-side,
the API returns JSON only, and stale/cached responses are mitigated via the
`X-Content-Type-Options: nosniff` header.

### CSRF

The API is an API-first backend using JWT bearer authentication. Tokens are
sent via the `Authorization` header (not cookies) with `Content-Type:
application/json`, so cross-site requests cannot forge authenticated calls.
As a result, no cookie-based CSRF protection is required. Cookie-mode
authentication, if ever introduced, must add CSRF tokens.

### Secrets management

Environment-specific secrets must be supplied via a secrets manager or
environment variables, never committed. The CI pipeline fails on Gitleaks
detection and dependency vulnerability audits (pip-audit, npm audit).

## Secret Management

- Never commit secrets to the repository
- Use environment variables or a secrets manager
- Rotate credentials regularly
- The `.env.example` file documents required variables — use `.env` for local development (gitignored)
