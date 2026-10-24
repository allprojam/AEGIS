# Aegis — the three diagrams

## 1. One cycle, end to end

```mermaid
flowchart TD
    T["timer / cron"] --> PF{"preflight"}
    PF -->|"missing module or API down"| STOP["exit 2 - nothing written"]
    PF -->|"ok"| RUN["aegis_run.py --top 60"]
    RUN --> SENSE["SENSE<br/>morpho_fetch.py reads Morpho API"]
    SENSE --> EVAL["EVALUATE<br/>lending_screen.py<br/>util, LLTV, liquidity, flags"]
    EVAL --> REASON{"REASON<br/>optional gemma3:12b"}
    REASON --> COMMIT["COMMIT<br/>runs/RUN_ID/"]
    COMMIT --> VERIFY{"VERIFY<br/>replay reproduces exactly?"}
    VERIFY -->|"drift"| FAIL["exit 1 - run kept, replay failed"]
    VERIFY -->|"exact"| DIFF["alert_diff.py<br/>append-only transition log"]
    DIFF --> STREAMS["liquidations.py then forward_test.py then velocity.py"]
    STREAMS --> PUB["publish.py"]
    PUB --> P1["1 of 3  export_report.py<br/>audits/RUN_ID.html - tear sheet"]
    P1 --> P2["2 of 3  build_v2.py<br/>report.html - dashboard"]
    P2 --> P3{"3 of 3  audit_parity.py<br/>do the two renderers agree?"}
    P3 -->|"AGREE"| LIVE["serve_preview.py :8099<br/>tailnet path /aegis"]
    P3 -->|"DISAGREE"| TRIP["rc 2 - parity tripwire"]
```

Failure policy: once the run is committed and replay-verified, the value is banked.
Transitions, liquidations, velocity and publish may all fail without failing the cycle.
A stale dashboard is a lesser harm than a lost run.

## 2. Why a row is visible - five dimensions, one writer

```mermaid
flowchart TD
    R["row enters applyVisibility"] --> D{"is a drawer row?"}
    D -->|"yes"| SKIP["skip - its parent row owns it"]
    D -->|"no"| C1{"1 chain tab<br/>data-chain"}
    C1 -->|"mismatch"| HIDE["display none"]
    C1 -->|"pass"| C2{"2 watchlist<br/>VIS.watch"}
    C2 -->|"not pinned"| HIDE
    C2 -->|"pass"| C3{"3 time floor<br/>data-when vs slider"}
    C3 -->|"older"| HIDE
    C3 -->|"pass"| C4{"4 verdict<br/>data-verdict"}
    C4 -->|"other verdict"| HIDE
    C4 -->|"pass"| C5{"5 text query"}
    C5 -->|"no match"| HIDE
    C5 -->|"pass"| SHOW["display blank"]
    SHOW --> DRW{"row has a drawer?"}
    DRW -->|"yes"| DD["drawer visible IFF<br/>row visible AND class open"]
    DRW -->|"no"| DONE["counted as shown"]
    DD --> DONE
    HIDE --> DONE2["counted as hidden"]
```

Controls never write style.display themselves. They record intent in VIS and call the
one executor. Two writers of one property is what caused every tab/filter/drawer clash.

DOM contract: table.previousElementSibling is the filter box. Four layers read it, so
anything inserted between the filter and the table silently drops the query.

## 3. Verdict to action

```mermaid
flowchart LR
    M["Morpho market"] --> Q["utilisation, LLTV,<br/>liquidity, vol, bad debt"]
    Q --> REAL["REAL<br/>yield is genuine"]
    Q --> CAUTION["CAUTION<br/>thin or near LLTV"]
    Q --> AVOID["AVOID<br/>locked, 100pct util, absurd APY"]
    REAL --> A["deploy capital"]
    CAUTION --> B["watch, size down"]
    AVOID --> C["do not touch"]
```

Run 20261020T174249Z: 60 markets, 17 REAL, 5 CAUTION, 38 AVOID.
