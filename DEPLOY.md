# Deployment — live now, and what each option actually costs

## Two questions answered from the machine, not from assumption

### Q1: How is credit settlement handled?

**Built: `screener/ledger.py` — sqlite credit ledger, pay-per-audit.**

The earlier build used an **in-memory** token store that **reset on restart** — flagged at the time as
unusable for real money. It is now durable.

```
accounts(key, balance)          balances persist across restarts
orders(id, key, credits, usd, status, txhash)
usage(key, ts, ip)              free tier, 3/day per IP
```

**Key design decision — it refuses to give away paid audits by accident.** `create_order()` opens an
order in `PENDING` and credits **nothing**. Credits are applied only by `confirm_order()`, which is
meant to be called by a verifier that has checked the chain. **The API cannot credit an order on its own.**

**Tested end-to-end:**
```
new account      balance=0
order            ord_15dea91648664367b3fb  100 credits  $5.0  PENDING
balance before   0                      <- not credited while PENDING (correct)
confirm          credited=100  balance=100
double-confirm   {'error': 'already credited', 'status': 'PAID'}   <- refuses, no double credit
spend 1/2/3      free tier, 3/day
spend 4..n       draws down balance: 99, 98, 97
```

**Settlement options, ranked by cost and whether they need anything we don't have:**

| option | fees | needs | verdict |
|---|---|---|---|
| **x402 + Base USDC** | ~$0.001 gas | a verifier calling `confirm_order` after checking the tx | **best fit** — native to the 402 the API already returns |
| Direct Base USDC deposit | ~$0.001 gas | same verifier; manual top-ups | simplest, viable today |
| LemonSqueezy | 5% + $0.50 | account, KYC, merchant of record | **$0.50 fixed kills a $0.05 sale** |
| Stripe | 2.9% + $0.30 | account, KYC | same problem |

**At $0.05/audit the card processors are structurally wrong** — Stripe's $0.30 fixed fee is 6x the
price of the product. **Crypto micro-settlement is not an ideological choice here, it is the only
arithmetically viable one.** Bulk credits ($5 / 100 audits) are the only tier where a card fee makes
sense.

### Q2: Deployment target?

**Live right now, verified:**

```
https://srv1619135.tailf16ee8.ts.net/report.html
-> HTTP 200, 2,149,870 bytes
-> "Why per-audit" pricing present
-> address index present
```

**Method: `tailscale serve --bg 8099`.** Tailscale was already installed and already authenticated;
this gave **real HTTPS with a valid cert, zero installation, no DNS work, no open firewall port.**
The proxy terminates TLS and forwards to the local static server.

**Reach:** your Android device `devons-z-fold6` is on this tailnet and active, so the page opens on your
phone at that URL immediately. **It is tailnet-only** — not on the public internet.

| target | cost | verdict |
|---|---|---|
| **tailscale serve** | $0 | **live now.** Private, HTTPS, works on your phone. |
| Cloudflare Tunnel | $0 | needs `cloudflared` — **not installed.** Public hostname, DDoS cover. |
| VPS + nginx | $0 software | needs install; **public IP is `<srv-public-ip>`.** No TLS without a domain + certbot. |
| GitHub Pages | $0 | static only — **the API needs a server**, so this cannot host the whole product. |
| Vercel | $0–20/mo | static + serverless; **the API is stateful (sqlite)**, so it would need a real DB. |

## A correction worth recording

**I tried `apk add nginx` and it failed: `setsid: failed to execute apk: No such file or directory`.**

**This VPS is Ubuntu 24.04.4 LTS, not Alpine.** `apk` does not exist here. My instructions assumed an
Alpine environment from a different machine. `python3` 3.12, `node` v22.22.2 and `sqlite3` 3.45.1 are
present and were enough — **no install was needed for anything above.**

## Recommended path to public

1. **Now:** tailnet HTTPS, live, verified. Use it to demo.
2. **To go public:** `cloudflared tunnel` — free, no open ports, gives a hostname and TLS. It is one
   binary; it is not installed yet.
3. **Before charging:** wire a Base USDC verifier to `ledger.confirm_order()`. **Until then
   `/order` creates PENDING orders and no money moves** — the correct fail-safe direction.

## Still not done, honestly

- **No chain verifier.** `confirm_order()` exists and is guarded, but nothing calls it from a real
  deposit. **Settlement is stubbed, not live.**
- **No public hostname yet** (tailnet only).
- **Gemma prose layer still unwired**, though reachable at `100.90.251.75:11434`.
- The browser tool's client-side checks and the server's checks are **two implementations**. They were
  tested to agree on four cases, but they can drift. A parity test should run in CI.
