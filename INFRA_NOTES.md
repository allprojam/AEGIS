# Why the website didn't work — two separate environments

## The problem

I served the report on the VPS at `http://127.0.0.1:8099` and reported it as working. **It was working —
on the VPS.** The app's preview does not read the VPS.

## What I found

**There are two separate machines.**

| | VPS (where I did the analysis) | App workspace (what the preview serves) |
|---|---|---|
| path | `/root/agency_bot/workspace/aegis/` | `/workspace/` |
| contents | book, screener, all 20+ research docs | `gpu.js`, `package.json`, `tts-test.wav`, empty `enosys/` |
| tool | `run_command` (100.88.95.39) | `run_command` in the app env, `/workspace` |

**I wrote everything to the VPS and served it there. The preview was pointed at `/workspace`, which had
none of it.**

That is the entire bug, and it is my mistake — I never verified where the preview reads from.

## The good news: they are on a Tailscale network and can talk

```
from the app env -> VPS:8099            wget succeeded, pulled the report
from the VPS     -> http://100.90.251.75:11434    HTTP 200, models listed
```

**And `gpu.js` in `/workspace` answers the Ollama question I got wrong earlier:**

```javascript
export const OLLAMA_URL = "http://100.90.251.75:11434";
export const GPU_MODEL  = "gemma4:12b";
```

**Ollama is reachable at `100.90.251.75:11434`, not localhost.** I tested `localhost`, `172.17.0.1` and
`host.docker.internal` and correctly reported all three refused — **but I never tested the Tailscale IP
that was documented in the project's own `gpu.js` file.** That file was in the app workspace the whole
time.

**Verified now:**
```
http://100.90.251.75:11434/api/tags   HTTP 200
  {"models":[{"name":"gemma4:12b",...}]}
```

**So the Gemma layer is not untested-and-blocked. It is reachable, and I simply looked in the wrong
three places.**

## The fix, applied

```
cp report.html -> /workspace/report.html
python3 -m http.server 8000 --bind 0.0.0.0   (in /workspace, backgrounded)
-> HTTP 200, 22,145 bytes, Content-Length confirmed
```

**Preview URL: http://127.0.0.1:8000/report.html**

## What this changes

**1. The report is now visible to you.** That was the actual request.

**2. The Gemma prose layer can be tested for real.** `verdict.py` and `auditread.py` both take an
injected transport. Pointing them at `http://100.90.251.75:11434/api/generate` with `gemma4:12b` is
a two-line change — and it will work, because the endpoint answers.

**3. Any future deliverable must be written to `/workspace`,** not just the VPS, or it is invisible.

## The honest lesson

**I reported "serving at 127.0.0.1:8099" and verified it with HTTP 200 — and it still did not work for
you.** A local curl proves the server runs; it does not prove it runs *where the user can see*.

That is the same class of error as the 24.04% outlier and the mislabeled data file: **I verified the
thing I controlled, not the thing that mattered.** Three times now. The fix is to test against the
user's actual path, not the nearest available proxy for it.
