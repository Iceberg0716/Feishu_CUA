from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class TemplateRenderError(ValueError):
    pass


_EXPR_RE = re.compile(r"{{\s*(.+?)\s*}}")
_ROOT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TemplateScope:
    params: dict[str, Any]
    vars: dict[str, Any]

    def resolve_root(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if name in self.params:
            return self.params[name]
        raise TemplateRenderError(f"unknown variable: {name}")


def _parse_access(expr: str) -> list[tuple[str, Any]]:
    """
    Parse a minimal access expression like:
      chat_candidate.click_point[0]
      search_shot.path
    into a list of tokens: [("root", "chat_candidate"), ("key", "click_point"), ("index", 0)]
    """
    s = expr.strip()
    if not s:
        raise TemplateRenderError("empty expression")

    i = 0
    n = len(s)

    def _read_name(start: int) -> tuple[str, int]:
        j = start
        while j < n and (s[j].isalnum() or s[j] == "_"):
            j += 1
        name = s[start:j]
        if not name or not _ROOT_NAME_RE.match(name):
            raise TemplateRenderError(f"invalid name in expression: {expr}")
        return name, j

    tokens: list[tuple[str, Any]] = []
    root, i = _read_name(0)
    tokens.append(("root", root))

    while i < n:
        ch = s[i]
        if ch == ".":
            i += 1
            if i >= n:
                raise TemplateRenderError(f"trailing '.' in expression: {expr}")
            name, i = _read_name(i)
            tokens.append(("key", name))
            continue
        if ch == "[":
            i += 1
            j = s.find("]", i)
            if j < 0:
                raise TemplateRenderError(f"missing ']' in expression: {expr}")
            inner = s[i:j].strip()
            if not inner:
                raise TemplateRenderError(f"empty index in expression: {expr}")
            try:
                idx = int(inner)
            except Exception:
                # allow ["key"] without quotes for simplicity? no.
                raise TemplateRenderError(f"non-integer index '{inner}' in expression: {expr}")
            tokens.append(("index", idx))
            i = j + 1
            continue
        raise TemplateRenderError(f"unsupported character '{ch}' in expression: {expr}")

    return tokens


def _eval_expr(expr: str, scope: TemplateScope) -> Any:
    tokens = _parse_access(expr)
    cur = scope.resolve_root(str(tokens[0][1]))
    for kind, val in tokens[1:]:
        if kind == "key":
            key = str(val)
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
                continue
            if hasattr(cur, key):
                cur = getattr(cur, key)
                continue
            raise TemplateRenderError(f"key '{key}' not found while evaluating: {expr}")
        if kind == "index":
            idx = int(val)
            if isinstance(cur, (list, tuple)):
                try:
                    cur = cur[idx]
                except Exception as exc:
                    raise TemplateRenderError(f"index {idx} out of range while evaluating: {expr}") from exc
                continue
            raise TemplateRenderError(f"cannot index non-list value while evaluating: {expr}")
        raise TemplateRenderError(f"unsupported token kind: {kind}")
    return cur


class TemplateRenderer:
    def render(self, value: Any, *, params: dict[str, Any], vars: dict[str, Any]) -> Any:
        scope = TemplateScope(params=params, vars=vars)
        return self._render_any(value, scope=scope)

    def _render_any(self, value: Any, *, scope: TemplateScope) -> Any:
        if isinstance(value, str):
            return self._render_str(value, scope=scope)
        if isinstance(value, dict):
            return {k: self._render_any(v, scope=scope) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_any(v, scope=scope) for v in value]
        return value

    def _render_str(self, template: str, *, scope: TemplateScope) -> Any:
        matches = list(_EXPR_RE.finditer(template))
        if not matches:
            return template

        # If the entire string is exactly one expression, return the raw value
        # (so ints stay ints, lists stay lists, etc.).
        if len(matches) == 1 and matches[0].span() == (0, len(template)):
            expr = matches[0].group(1)
            return _eval_expr(expr, scope)

        def _sub(m: re.Match[str]) -> str:
            expr = m.group(1)
            v = _eval_expr(expr, scope)
            return "" if v is None else str(v)

        return _EXPR_RE.sub(_sub, template)


__all__ = ["TemplateRenderer", "TemplateRenderError"]

