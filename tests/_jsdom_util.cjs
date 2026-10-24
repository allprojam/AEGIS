/* _jsdom_util.cjs - load report.html and EXECUTE its functions, instead of grepping source.
 *
 * WHY THIS EXISTS. tests/test_lookup.cjs and tests/test_table.cjs read the raw text of app.js and
 * table.js and searched it with indexOf/regex. That has the same failure mode already eliminated
 * on the Python side: the check passes on a COMMENT that mentions the code, and breaks when the
 * code is merely reformatted or an identifier is renamed. Worse, it cannot see what the code
 * DOES -- "offers a next step that resolves it" is a claim about behaviour that a substring can
 * only approximate.
 *
 * The page is self-contained (no external scripts, on purpose -- asserted elsewhere), so loading
 * it in jsdom gives a REAL window with every function the page defines. Ask that window.
 */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.dirname(__dirname);

/* Load report.html with scripts executed. Returns { dom, window, document, settle }.
 * `settle` resolves once the page's own initialiser has run, so callers can `await` it rather
 * than guessing a sleep -- a fixed timeout is the flakiest thing in this kind of test. */
function load(page = path.join(ROOT, "report.html")) {
  const vc = new VirtualConsole();               // swallow console noise from the page itself
  const dom = new JSDOM(fs.readFileSync(page, "utf8"), {
    runScripts: "dangerously", pretendToBeVisual: true, url: "https://example.test/",
    virtualConsole: vc,
  });
  const ready = new Promise((resolve) => {
    dom.window.addEventListener("load", () => setTimeout(resolve, 50));
    setTimeout(resolve, 1500);                   // hard ceiling so a broken page cannot hang the suite
  });
  return { dom, window: dom.window, document: dom.window.document, ready };
}

/* Call a page function by name and return its VALUE. Throws a clear error when the function is
 * absent, because "function not defined" and "function returned nothing useful" are different
 * faults and should not look alike. */
function call(window, name, ...args) {
  if (typeof window[name] !== "function") {
    throw new Error("page does not define " + name +
                    "() -- it was renamed, or the script did not run");
  }
  return window[name](...args);
}

/* Extract the text of a rendered fragment as plain text, for asserting on what a USER reads
 * rather than on the markup that produced it. */
function textOf(node) {
  if (!node) return "";
  return (node.textContent || "").replace(/\s+/g, " ").trim();
}

/* Every anchor inside a node, as {href, text, title}. Lets a test assert on resolved links
 * without any HTML string matching. */
function anchors(node) {
  if (!node) return [];
  return Array.from(node.querySelectorAll("a")).map((a) => ({
    href: a.getAttribute("href") || "",
    text: (a.textContent || "").trim(),
    title: a.getAttribute("title") || "",
  }));
}

/* Run a list of assertions and report in the same shape as the other suites. */
function reporter() {
  const fails = [];
  const ck = (name, cond, detail) => {
    console.log("  " + name.padEnd(62) + (cond ? "PASS" : "FAIL"));
    if (!cond) {
      if (detail) console.log("      " + detail);
      fails.push(name);
    }
  };
  return { ck, fails };
}

module.exports = { ROOT, load, call, textOf, anchors, reporter };
