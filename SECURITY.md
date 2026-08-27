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
- Rate limiting middleware (per-IP sliding window)
- Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, Permissions-Policy)
- Input validation via Pydantic models
- SQL injection prevention via SQLAlchemy ORM
- CORS configuration (origin-restricted)
- Dependency vulnerability scanning via pip-audit and npm audit
- Container image scanning via Trivy in CI/CD

## Secret Management

- Never commit secrets to the repository
- Use environment variables or a secrets manager
- Rotate credentials regularly
- The `.env.example` file documents required variables — use `.env` for local development (gitignored)
