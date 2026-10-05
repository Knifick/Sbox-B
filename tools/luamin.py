"""Lua 5.1 -> single-line Sobixel-safe text.

Rules derived from how Sobixel runs `requestApi` text (see README):
  * one physical line: no LF/CR/TAB anywhere,
  * no backslash at all (escape handling is not reliable through the
    JSON -> Sobixel -> loadstring chain), so strings must be escape-free,
  * no `--` (would comment out the rest of the program),
  * no long brackets `[[ ]]` / `[=[`, and `]]` is always split into `] ]`,
  * ASCII only,
  * the literal identifier getCurrentStage must not appear.
Comments are stripped, whitespace is collapsed to the minimum the lexer needs.
"""
import re
import subprocess
import sys
import tempfile

KEYWORDS = {
    'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for', 'function',
    'if', 'in', 'local', 'nil', 'not', 'or', 'repeat', 'return', 'then',
    'true', 'until', 'while'}

TOKEN_RE = re.compile(r'''
    (?P<ws>[ \t\r\n]+)
  | (?P<lcomment>--\[(?P<eq>=*)\[.*?\](?P=eq)\])
  | (?P<comment>--[^\n]*)
  | (?P<lstring>\[(?P<eq2>=*)\[.*?\](?P=eq2)\])
  | (?P<string>"[^"\n]*"|'[^'\n]*')
  | (?P<number>0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\.\.\.|\.\.|==|~=|<=|>=|[-+*/%^\#<>=(){}\[\];:,.])
''', re.S | re.X)


class MinifyError(Exception):
    pass


def tokenize(src, fname='?'):
    pos = 0
    out = []
    line = 1
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise MinifyError('%s:%d: cannot tokenize near %r' % (fname, line, src[pos:pos + 30]))
        kind = m.lastgroup
        text = m.group(0)
        if kind in ('eq', 'eq2'):
            kind = 'lcomment' if text.startswith('--') else 'lstring'
        if kind == 'lstring':
            raise MinifyError('%s:%d: long strings are not allowed' % (fname, line))
        if kind == 'string' and '\\' in text:
            raise MinifyError('%s:%d: backslash escapes are not allowed: %s' % (fname, line, text))
        if kind not in ('ws', 'comment', 'lcomment'):
            out.append((kind, text, line))
        line += text.count('\n')
        pos = m.end()
    return out


def _is_word(t):
    return t[0] in ('name', 'number') or t[1] in KEYWORDS


def join(tokens):
    parts = []
    prev = None
    for t in tokens:
        s = t[1]
        if prev is not None:
            p = prev[1]
            need = False
            if _is_word(prev) and _is_word(t):
                need = True
            elif prev[0] == 'number' and (s.startswith('.') or s[0].isalnum() or s[0] == '_'):
                need = True
            elif p.endswith('.') and t[0] == 'number':
                need = True
            elif p == '-' and s.startswith('-'):
                need = True
            elif p.endswith('[') and (s.startswith('[') or s.startswith('=')):
                need = True
            elif p.endswith(']') and s.startswith(']'):
                need = True
            elif p in ('.', '..') and s.startswith('.'):
                need = True
            elif p in ('<', '>', '=', '~') and s.startswith('='):
                need = True
            elif p.endswith('=') and s.startswith('='):
                need = True
            if need:
                parts.append(' ')
        parts.append(s)
        prev = t
    return ''.join(parts)


FORBIDDEN = [
    ('\n', 'newline'), ('\r', 'carriage return'), ('\t', 'tab'), ('\\', 'backslash'),
    ('--', 'comment marker'), ('[[', 'long bracket'), (']]', 'long bracket close'),
    ('[=', 'long bracket'), ('getCurrentStage', 'blocked identifier'),
]


# Sobixel rewrites "pcall(function" in requestApi text to its SAFE_RUN, which
# is not reachable from there ("attempt to call global 'SAFE_RUN'")
FORBIDDEN_RE = [(re.compile(r'pcall\s*\(\s*function'), 'pcall(function (Sobixel rewrites it to SAFE_RUN)')]


def validate(text, fname='?'):
    for rx, what in FORBIDDEN_RE:
        mm = rx.search(text)
        if mm:
            i = mm.start()
            raise MinifyError('%s: forbidden %s at %d: %r' % (fname, what, i, text[max(0, i - 40):i + 40]))
    for needle, what in FORBIDDEN:
        i = text.find(needle)
        if i >= 0:
            raise MinifyError('%s: forbidden %s at %d: %r' % (fname, what, i, text[max(0, i - 40):i + 40]))
    bad = [c for c in text if ord(c) > 126 or ord(c) < 32]
    if bad:
        raise MinifyError('%s: non-printable/non-ASCII characters: %r' % (fname, bad[:5]))


def luac_check(text, fname='?', luac='luac5.1'):
    with tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False) as f:
        f.write(text)
        path = f.name
    r = subprocess.run([luac, '-p', path], capture_output=True, text=True)
    if r.returncode != 0:
        raise MinifyError('%s: luac: %s' % (fname, r.stderr.strip()[-600:]))


def minify(src, fname='?', check=True):
    text = join(tokenize(src, fname))
    validate(text, fname)
    if check:
        luac_check(text, fname)
    return text


if __name__ == '__main__':
    # python3 luamin.py file.lua [--no-luac]  ->  the one-line text for a requestApi block on stdout
    use_luac = '--no-luac' not in sys.argv
    for p in [a for a in sys.argv[1:] if a != '--no-luac']:
        text = minify(open(p).read(), p, check=False)
        validate(text, p)
        if use_luac:
            luac_check(text, p)
        sys.stdout.write(text + '\n')
