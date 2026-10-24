# Security

## No funds, no keys

This repository contains **no wallet keys, no signing code, and no code path
that can move funds.** Verified by grep: no `private_key`, no
`eth_sendRawTransaction`, no signer of any kind.

If you find anything that contradicts that, treat it as a critical issue.

## Reporting

Open a private security advisory on GitHub, or email the maintainer.
Do not open a public issue for anything that could be exploited.

## Licensing secret

The hosted screener issues access tokens signed with an HMAC secret
(`screener/token_secret.key`). That file is **not** in this repository and
never will be — it is gitignored, and the published history contains no
commit that ever included it.

If you are running your own deployment, generate your own:

```bash
python3 -c "import secrets; open('screener/token_secret.key','w').write(secrets.token_urlsafe(48))"
chmod 600 screener/token_secret.key
```

## Dependencies

The screening pipeline depends on the Python standard library and public
HTTP APIs (Morpho GraphQL, DefiLlama). No API keys are required. Verify
upstream data with `provenance.py` before acting on any figure.

## Scope

In scope: the screeners, the MCP server, the allocator's arithmetic.
Out of scope: the third-party protocols being screened. This tool measures
them; it does not secure them.
