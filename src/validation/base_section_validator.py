from __future__ import annotations

import re
from typing import Callable, Optional


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def base_section_validator(*, min_chars_no_spaces: int = 900) -> Callable[[str], Optional[str]]:
    def _v(text: str) -> Optional[str]:
        t = (text or "").strip()
        if not t:
            return "empty_output"
        if len(_strip_spaces(t)) < int(min_chars_no_spaces):
            return "too_short"
        return None
    return _v





    
