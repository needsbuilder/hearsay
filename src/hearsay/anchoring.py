"""Anchoring: a quote only counts if its passage is about the claim's symbol.

The quote rule proves that a quote exists in the documentation. Anchoring
checks that the passage holding it is about the symbol the claim names, so
a line from the `fs.rmdir` section cannot decide a claim about `fs.rm`.

The rule, in two steps:

1. If the passage sits under an API heading (a heading that is a call
   signature such as `fs.rmdir(path[, options], callback)`, or a Sphinx
   definition such as `classmethod datetime.utcnow()`), the nearest such
   heading decides alone: it must name the symbol. Other functions mentioned
   in that section's text are cross-references and do not count.
2. Otherwise the passage's heading path or its text must name the symbol.

"Names the symbol" means one of these written forms appears as a whole name
(not followed by more identifier characters, so `fs.rmdir` does not name
`fs.rm`):

- the dotted name, or a dotted suffix of two or more parts:
  `fs.rm`, `datetime.datetime.utcnow` (names `datetime.utcnow`);
- the same name with an owner alias: `fsPromises.rm`, `fs.promises.rm`;
- the name with a space after its last dot and a call after it, which is how
  Tavily's Markdown renders code samples: `requests. get(`;
- the possessive form: `datetime.datetime's utcnow()`;
- for a one-part symbol (a module), the bare name: `distutils`.

Link targets count as text, because Sphinx cross-references carry the
qualified name there: `[utcnow()](...#datetime.datetime.utcnow)`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Claim, Passage
from .quotes import normalize

IDENT = r"[A-Za-z_$][\w$]*"

# Owners that the documentation writes under another name.
OWNER_ALIASES: dict[str, tuple[str, ...]] = {
    "fs": ("fsPromises", "fs.promises"),
}

# A heading that is a call signature: an identifier (dotted or not)
# directly followed by "(". "Python (programming)" is not one.
_SIGNATURE = re.compile(rf"(?<![\w$]){IDENT}(?:\.{IDENT})*\(")
_LINK_TARGET = re.compile(r"\]\([^)\s]*#([A-Za-z_$][\w$.]*)")
_LINK_TITLE = re.compile(r"\]\([^)]*\"([A-Za-z_$][\w$.]*)\"\)")


def is_api_heading(heading: str) -> bool:
    return bool(_SIGNATURE.search(normalize(heading)))


def names_text(raw: str) -> str:
    """Text to search for names: the normalised text plus link targets and titles."""
    targets = _LINK_TARGET.findall(raw) + _LINK_TITLE.findall(raw)
    return normalize(raw) + ("\n" + "\n".join(targets) if targets else "")


@dataclass(frozen=True)
class Anchor:
    symbol: str  # as the claim wrote it
    parts: tuple[str, ...]  # ("fs", "rm")

    @classmethod
    def parse(cls, symbol: str) -> "Anchor | None":
        s = normalize(symbol)
        s = s.split("(", 1)[0].strip()  # drop call arguments: fs.rm(path) -> fs.rm
        parts = tuple(p for p in re.split(r"\.|::|#", s) if p)
        if not parts or not all(re.fullmatch(IDENT, p) for p in parts):
            return None
        return cls(symbol, parts)

    @classmethod
    def for_claim(cls, claim: Claim) -> "Anchor | None":
        return cls.parse(claim.symbol) if claim.symbol else None

    @property
    def name(self) -> str:
        return ".".join(self.parts)

    def written_forms(self) -> list[str]:
        """The literal names that count (before the whole-name check)."""
        parts = self.parts
        if len(parts) == 1:
            return [parts[0]]
        forms = [".".join(parts[i:]) for i in range(len(parts) - 1)]
        owner, last = ".".join(parts[:-1]), parts[-1]
        forms += [f"{alias}.{last}" for alias in OWNER_ALIASES.get(owner, ())]
        return forms

    def pattern(self) -> re.Pattern[str]:
        alternatives = []
        for form in self.written_forms():
            alternatives.append(re.escape(form))
            if "." in form:
                head, last = form.rsplit(".", 1)
                alternatives.append(rf"{re.escape(head)}\. {re.escape(last)}(?=\()")  # requests. get(
        if len(self.parts) >= 2:
            owner_last = self.parts[-2]
            alternatives.append(rf"{re.escape(owner_last)}'s {re.escape(self.parts[-1])}")
        return re.compile(r"(?<![\w$])(?:" + "|".join(alternatives) + r")(?![\w$])")

    def named_in(self, raw: str) -> bool:
        return bool(self.pattern().search(names_text(raw)))

    def problem(self, passage: Passage) -> str | None:
        """None if the passage is about this symbol, otherwise why not."""
        if passage.api_heading is not None:
            if self.named_in(passage.api_heading):
                return None
            return f"the quote is in the section for {normalize(passage.api_heading)!r}, not {self.name}"
        if self.named_in("\n".join(passage.section)) or self.named_in(passage.text):
            return None
        return f"the quoted passage does not name {self.name}"
