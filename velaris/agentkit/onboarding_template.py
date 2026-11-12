"""A safe template engine: `{name}` placeholders from a whitelist, nothing else.

Why not str.format: format strings can reach attributes and items (`{x.__class__}`, `{x[0]}`) and apply format
specs. Here a template is parsed with string.Formatter().parse() and accepted only if every field is a bare
identifier with no conversion and no format spec; `{{` and `}}` are literal braces. Rendering is by plain
substitution of the supplied values, so a template cannot run, import, read an attribute or loop.

  validate(template, allowed)   the problems (empty list = fine): unknown placeholder, syntax, size
  render(template, values, allowed, html=False)
                                the text; a placeholder with no value, or a value that is not a string, an
                                int or a Decimal, raises TemplateError. html=True escapes every value.
"""
from __future__ import annotations

import html as _html
import re
import string
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Set

MAX_TEMPLATE = 20000
MAX_VALUE = 4000
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TemplateError(ValueError):
    """The template or a value is not acceptable. The message names the placeholder."""


def _fields(template: str) -> List[str]:
    if not isinstance(template, str) or not template.strip() or len(template) > MAX_TEMPLATE:
        raise TemplateError(f"a template must be 1 to {MAX_TEMPLATE} characters")
    names = []
    try:
        for _lit, field, spec, conv in string.Formatter().parse(template):
            if field is None:
                continue
            if not _IDENT.match(field) or spec or conv:
                raise TemplateError(f"placeholder {{{field}{'!' + conv if conv else ''}{':' + spec if spec else ''}}} is not a plain name")
            names.append(field)
    except ValueError as e:
        raise TemplateError(f"template syntax: {e}") from e
    return names


def placeholders(template: str) -> Set[str]:
    return set(_fields(template))


def validate(template: str, allowed: Iterable[str]) -> List[str]:
    try:
        used = placeholders(template)
    except TemplateError as e:
        return [str(e)]
    return [f"unknown placeholder {{{n}}}" for n in sorted(used - set(allowed))]


def render(template: str, values: Dict[str, Any], allowed: Iterable[str], *, html: bool = False) -> str:
    problems = validate(template, allowed)
    if problems:
        raise TemplateError("; ".join(problems))
    out = []
    for literal, field, _spec, _conv in string.Formatter().parse(template):
        out.append(literal)
        if field is None:
            continue
        if field not in values:
            raise TemplateError(f"no value for placeholder {{{field}}}")
        v = values[field]
        if isinstance(v, bool) or not isinstance(v, (str, int, Decimal)):
            raise TemplateError(f"value for {{{field}}} must be text or a number")
        text = str(v)
        if len(text) > MAX_VALUE:
            raise TemplateError(f"value for {{{field}}} is longer than {MAX_VALUE} characters")
        out.append(_html.escape(text) if html else text)
    return "".join(out)
