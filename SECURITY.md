# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability** feature instead of opening a public issue. Include the affected route or component, reproduction steps, impact, and any suggested mitigation.

## Security design

- Uploaded files are limited by size and an explicit extension allowlist.
- Text input is length-bounded and model prompts treat document content as untrusted data.
- The local API exposes a restricted CORS allowlist rather than wildcard credentials.
- The AWS template blocks public S3 access, encrypts S3/SQS/DynamoDB data, uses pre-signed uploads, applies least-privilege policies, and expires documents after seven days.
- Environment files, credentials, private keys, build output, and local AWS state are excluded from version control.
- Unknown or invalid documents require human review and are never silently approved.

Do not use the application as the sole decision-maker for financial, legal, medical, employment, or other high-impact workflows.
