# apps/technology/templatetags/html_extras.py
from django import template
import re

register = template.Library()

# Matches <li>  (any mix of spaces, &nbsp;, non-breaking space, <br/>)  </li>
EMPTY_LI_RE = re.compile(
    r"<li>\s*(?:&nbsp;|\u00a0|\s|<br\s*/?>)*</li>",
    flags=re.IGNORECASE
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE  = re.compile(r"(?:\s|&nbsp;|\u00a0)+")

def _normalized_text(html: str) -> str:
    """Remove empty <li>, then strip all tags/whitespace; return leftover text."""
    if not html:
        return ""
    s = EMPTY_LI_RE.sub("", html)       # remove empty <li>…</li>
    s = TAG_RE.sub("", s)                # remove all tags
    s = WS_RE.sub(" ", s)                # collapse whitespace, &nbsp;, NBSP
    return s.strip()

@register.filter
def has_content(html: str) -> bool:
    """True if HTML has any *real* text after removing empty bullets."""
    return bool(_normalized_text(html))

@register.filter
def only_empty_bullets(html: str) -> bool:
    """
    True if it *looks* like a UL but contains no real text—i.e., only empty LIs.
    """
    if not html:
        return False
    lower = html.lower()
    had_ul = "<ul" in lower
    return had_ul and not has_content(html)
