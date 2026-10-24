# USR / Resolv teardown — draft, with a hard limit stated up front

**DRAFT. Not published. One line in the brief needs correcting before this goes out.**

---

## The correction I have to make first

The brief says the teardown *"needs to show that an isolated market running at a 91.5% LLTV with
100% utilisation on a synthetic stablecoin violates basic structural safety margins."*

**The live readings are real, but they are the state AFTER the exploit, not before it.** That
distinction decides whether this piece is marketing or misinformation.

Measured from the market's own history:

```
USR market, Morpho Blue on Base
  LLTV 91.5%

  utilisation       2025-12-18  86.5%   ->   2026-10-07  100.0%
  supply APY        2025-12-18  0.59%   ->   2026-10-07  297,995%
  liquidity (USD)   2025-12-18  $1,574  ->   2026-10-07  $0.001
```

**So we cannot say "we would have stopped you entering."** We have no evidence the market carried a
RED warning, or sat at 100% utilisation, *before* Resolv was exploited. **What we can say is that it
is broken now, and that the flags read correctly on a market we know failed.**

**Claiming otherwise would be exactly the 241.5% share and the circular stress test, in public, with a
protocol's name on it.**

---

## What IS verifiable, and it is damning

**The exploit itself.** Resolv's USR, March 2026:

```
CoinDesk      "Resolv stablecoin crashes 70% as attacker extracts $25 million in ETH"
The Block     "attacker mints 80 million unbacked tokens, extracts roughly $25 million"
Halborn       "Explained: The Resolv Hack (March 2026)"
CoinMarketCap "Morpho Falls 4.6% After Resolv Exploit Hits Vaults"
```

**An attacker minted ~80M unbacked USR.** Not a market moving — a supply number that should not
have existed. **No structural filter on a lending market catches a key compromise.** That is an
honest and important thing for us to say out loud, because it bounds what any screen can do.

**The aftermath, measured today:**

```
market id   0xff0f2bd5...d03f89
collateral  USR   (0x35E5dB674D8e93a03d814FA0ADa70731efe8a4b9)
oracle      0xa40E4a5C4ff8ec8ae05648A4F34E02CeD8Ae9EFB

supplied          $36,713,317
bad debt          $34,821,390      <- 95% of supply
realised          $0               <- still unrealised
utilisation       100.00%
liquidity         $0.001           <- effectively zero
net APY           297,996%
LLTV              91.5%

Morpho's own warnings:
  RED     bad_debt_unrealized
  RED     oracle_price_derivation
  YELLOW  not_whitelisted
```

**$34.8M of $36.7M supplied is bad debt.** The market holds a thousandth of a dollar of withdrawable
liquidity and is quoting a 297,996% supply rate. **The screen flags it `AVOID` on four independent
grounds.**

---

## The honest framing

**What the piece can say:**

> **On 22 March 2026 an attacker minted roughly 80 million unbacked USR and extracted about $25M.**
> **Today the USR market on Morpho Blue carries $34.8M of bad debt against $36.7M supplied — 95% —
> with a thousandth of a dollar of withdrawable liquidity, and quotes a 297,996% supply rate.**
> **Morpho itself flags it RED twice: `bad_debt_unrealized` and `oracle_price_derivation`.**
>
> **Our screen marks it AVOID on four grounds. A structural screen cannot stop a key compromise —
> nothing on-chain could have. What it can do is refuse to treat a market holding $0.001 of
> liquidity as a place to put capital, and the flag would have been correct every day since.**

**What it cannot say:** that we predicted it, or that our rules would have kept anyone out before the
fact. We do not have the pre-exploit data to support that, and **the tool is built precisely to not
make claims like that.**

---

## Why this is still the right marketing asset

**Because it demonstrates restraint.** A teardown that says *"here is a failure, here is what our
tool reads on it now, and here is what it could not have prevented"* is more credible than one
claiming prescience. **Every competitor's post-mortem claims to have seen it coming. This one says
plainly what it saw and when.**

**And it makes the limit explicit, which is the brand:** *a structural screen reads structure. It
does not read private keys.*

---

## Draft

### Teardown: USR on Morpho Blue

**On 22 March 2026, Resolv's USR stablecoin was exploited.** An attacker minted roughly 80 million
unbacked tokens and extracted approximately $25M. USR depegged, falling 70–80%. Morpho's own token
fell 4.6% as the loss hit its vaults.

**Seven months later, the USR market on Morpho Blue (Base) reads like this:**

| | |
|---|---|
| supplied | $36,713,317 |
| bad debt | **$34,821,390** |
| share of supply lost | **95%** |
| withdrawable liquidity | **$0.001** |
| utilisation | **100.00%** |
| net supply APY | **297,996%** |
| LLTV | 91.5% |

**Morpho's own API flags this market RED twice** — `bad_debt_unrealized` and
`oracle_price_derivation` — and additionally notes `not_whitelisted` at yellow.

**Aegis flags it `AVOID` on four independent grounds:** realised bad debt, a RED protocol warning,
utilisation above the exit threshold, and an APY two orders of magnitude outside any lending rate.

**What this does not show.** A structural screen reads structure. **It cannot read a private key.** No
on-chain filter would have prevented an unauthorised mint, and we do not claim ours would have. What
we can show is that once the damage existed, the market was never again a defensible place for
capital — and that a screen holding it to a liquidity floor, a utilisation ceiling and a bad-debt
exclusion would have refused it **every single day since.**

**That is the whole value of a current-state risk assessment.** It does not tell you what will happen.
It tells you what is true right now, and refuses to look away from it.

---

## Verification before publish

- [ ] Confirm the market address and oracle on a block explorer
- [ ] Confirm the USR token address `0x35E5dB...8a4b9` is Resolv's USR, not a namesake
- [ ] Cite each news source with a link and date
- [ ] State the pre-exploit data limitation explicitly (do not bury it)
- [ ] Include the raw JSON so any reader can reproduce the table
- [ ] Have someone who is not us check the claim that we would *not* have caught it
