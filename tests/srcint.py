"""srcint.py - inspect Python source STRUCTURALLY, not by substring.

WHY THIS EXISTS. Assertions like `"timeout=300" in src` and `"rmtree" not in src` pass when the
string appears in a COMMENT and fail when the code is merely REFORMATTED. Both happened in this
project: an assertion failed on its own explanatory comment, twice. The fix is to ask the AST
what the code DOES rather than what the file SAYS.

Comments and docstrings do not exist in an AST, so the false positives disappear by construction
rather than by careful wording.

WHAT IT CANNOT DO. It is not a sandbox and makes no claim about runtime behaviour. An import that
rebinds a name, a getattr, or a call through a variable is invisible here. Use it for structural
facts -- "this call passes timeout=", "this module imports subprocess", "this function returns 2"
-- and use a real execution when the question is what the program DOES.
"""
import ast, io, tokenize


def parse(path):
    """Parse a file, tolerating any encoding declaration."""
    with open(path, "rb") as f:
        return ast.parse(f.read(), filename=path)


def _iter_calls(tree, func_name=None):
    """Every ast.Call, optionally only those whose callee matches `func_name`.

    Matching is on the attribute or bare name as written, so `subprocess.run` matches func_name
    "run" and "subprocess.run". A call through a variable is deliberately NOT matched -- guessing
    resolution is how structural checks start lying.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        names = []
        if isinstance(f, ast.Attribute):
            names.append(f.attr)
            if isinstance(f.value, ast.Name):
                names.append(f.value.id + "." + f.attr)
        elif isinstance(f, ast.Name):
            names.append(f.id)
        if func_name is None or func_name in names:
            yield node


def call_kwargs(path, func_name, kwarg):
    """All VALUES passed as `kwarg=` to every call of func_name, as AST nodes.

    Used to assert a timeout is present on a call WITHOUT depending on how it is spelled or
    whether a comment nearby mentions it.
    """
    out = []
    for c in _iter_calls(parse(path), func_name):
        for kw in c.keywords:
            if kw.arg == kwarg:
                out.append(kw.value)
    return out


def call_positions(path, func_names):
    """Line numbers of calls to any of func_names, in source order.

    The ordering of calls is a REAL invariant (publish.py must export the tear sheet before
    building the dashboard, or parity reports RUN_MISMATCH). Reading it from the AST keeps that
    assertion while removing its dependence on a comment happening to sit between the calls.
    """
    pos = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if name in func_names:
                pos.append((name, node.lineno))
    return sorted(pos, key=lambda t: t[1])


def called_names(path, func_name=None):
    """Every function/method NAME invoked anywhere in the file, as written."""
    seen = set()
    for c in _iter_calls(parse(path), func_name):
        f = c.func
        if isinstance(f, ast.Attribute):
            seen.add(f.attr)
            if isinstance(f.value, ast.Name):
                seen.add(f.value.id + "." + f.attr)
        elif isinstance(f, ast.Name):
            seen.add(f.id)
    return seen


def imported_modules(path):
    """Top-level module names imported, so 'import subprocess' can be asserted structurally."""
    mods = set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def function_returns(path, func_name):
    """Literal values returned by a named function, plus None for a bare `return`.

    Used to assert publish.py reserves exit code 2 for a parity DISAGREEMENT without matching the
    text " return 2", which a comment can satisfy.
    """
    out = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for n in ast.walk(node):
                if isinstance(n, ast.Return):
                    if n.value is None:
                        out.append(None)
                    elif isinstance(n.value, ast.Constant):
                        out.append(n.value.value)
                    elif isinstance(n.value, ast.Compare) and isinstance(n.value.left, ast.Constant):
                        # `return 0 if cond else 1` -- the left branch is the interesting one
                        out.append(n.value.left.value)
    return out


def strings_in_code(path):
    """Every string LITERAL in the file, EXCLUDING comments.

    Docstrings ARE included, because a docstring is a real object in the compiled module and can
    be read at runtime by help(). Comments are excluded, which is exactly the false positive that
    broke two assertions here. Prefer this over reading the file as text.
    """
    out = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def has_comment_mentioning(path, needle):
    """True if `needle` appears in a COMMENT or DOCSTRING. The inverse of what tests usually want:
    useful for asserting that a hazard is DOCUMENTED, without confusing it for the hazard itself.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and needle in tok.string:
            return True
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str) and needle in node.value.value:
            return True
    return False
