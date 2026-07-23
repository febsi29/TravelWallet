# Security Policy

## Supported version

Security fixes are applied to the latest commit on `main`.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting when it is available. Do not
open a public issue containing credentials, personal data, or exploit details.

## Credential handling

- Never commit API keys, access tokens, `.env` files, or local browser profiles.
- Copy `.env.example` to `.env` and provide credentials only through environment
  variables or deployment secret stores.
- Revoke a credential immediately if it is exposed. Removing it from the latest
  commit does not make an exposed credential safe.

## Demo data

The repository uses fictional demonstration identities. Do not add real travel
records, names, receipts, account identifiers, or payment information.
