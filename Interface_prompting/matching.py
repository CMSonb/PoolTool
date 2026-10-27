"""Ähnlichkeitsanalyse: ordnet Varianten aus den Daten Begriffen des Vokabulars zu.

Schnittstelle (für eigene Matcher, z. B. CLIP):

    class MeinMatcher(BaseMatcher):
        def match(self, variants, vocab_terms, threshold, progress=None):
            -> {Vokabelbegriff: [(Variante, Ähnlichkeit 0–1), ...]}

Jede Variante soll höchstens EINEM Vokabelbegriff zugeordnet werden (dem ähnlichsten,
sofern Ähnlichkeit >= threshold). Danach in ``get_matcher`` registrieren und in
config.py ``MATCHER`` setzen.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Optional

try:
    from rapidfuzz import fuzz

    def _ratio(a: str, b: str) -> float:
        return fuzz.ratio(a, b) / 100.0

    def _token_sort(a: str, b: str) -> float:
        return fuzz.token_sort_ratio(a, b) / 100.0

except ImportError:  # Fallback ohne rapidfuzz (langsamer)
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _token_sort(a: str, b: str) -> float:
        return _ratio(" ".join(sorted(a.split())), " ".join(sorted(b.split())))


Progress = Optional[Callable[[int, int], None]]


class BaseMatcher:
    name = "base"

    def match(
        self, variants: list[str], vocab_terms: list[str], threshold: float, progress: Progress = None
    ) -> dict[str, list[tuple[str, float]]]:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Standard: Zeichenketten-Ähnlichkeit + leichte deutsche Normalisierung/Stammformen
# --------------------------------------------------------------------------

_REPL = (("ß", "ss"), ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ph", "f"), ("th", "t"), ("ck", "k"))
_SUFFIXES = ("ern", "em", "en", "er", "es", "e", "n", "s")
PREFIX_SCORE = 0.80


def normalize(text: str) -> str:
    t = text.lower().strip()
    for a, b in _REPL:
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[\W_]+", " ", t).strip()


def _stem_token(tok: str) -> str:
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def stem_text(norm: str) -> str:
    return " ".join(_stem_token(t) for t in norm.split())


class StringMatcher(BaseMatcher):
    """Foto / Fotos / Fotographie / Photographie -> Fotografie."""

    name = "string"

    def match(self, variants, vocab_terms, threshold, progress=None):
        vocab = []
        for term in vocab_terms:
            n = normalize(term)
            vocab.append((term, n, stem_text(n)))
        result: dict[str, list[tuple[str, float]]] = {t: [] for t in vocab_terms}
        total = len(variants)
        for count, variant in enumerate(variants, 1):
            nv = normalize(variant)
            if nv:
                sv = stem_text(nv)
                best_term, best = None, 0.0
                for term, nt, st in vocab:
                    s = max(_ratio(sv, st), _ratio(nv, nt), _token_sort(sv, st))
                    short, long_ = (sv, st) if len(sv) <= len(st) else (st, sv)
                    if len(short) >= 4 and long_.startswith(short):
                        s = max(s, PREFIX_SCORE)
                    if s > best:
                        best_term, best = term, s
                if best_term is not None and best >= threshold:
                    result[best_term].append((variant, best))
            if progress and count % 200 == 0:
                progress(count, total)
        if progress:
            progress(total, total)
        return result


# --------------------------------------------------------------------------
# HOOK für CLIP (CPU) – von Ihnen zu ergänzen
# --------------------------------------------------------------------------


class ClipMatcher(BaseMatcher):
    """Platzhalter für die semantische Analyse mit CLIP (Text-Encoder, CPU).

    Vorschlag für die Umsetzung:
      1. Modell einmalig laden (z. B. sentence-transformers 'clip-ViT-B-32' /
         multilinguale Variante) und Vokabelbegriffe einmal einbetten.
      2. Varianten in Batches einbetten (``progress(done, total)`` regelmäßig aufrufen,
         damit das Interface den Fortschritt anzeigt).
      3. Kosinus-Ähnlichkeit berechnen, je Variante den besten Begriff wählen und bei
         Ähnlichkeit >= threshold als (Variante, Score) eintragen.
    Zusätzliche Pakete in requirements.txt (und ggf. Dockerfile) ergänzen.
    """

    name = "clip"

    def match(self, variants, vocab_terms, threshold, progress=None):
        raise NotImplementedError("Der CLIP-Matcher ist noch nicht implementiert (siehe matching.py).")


def get_matcher(name: str) -> BaseMatcher:
    matchers = {"string": StringMatcher, "clip": ClipMatcher}
    if name not in matchers:
        raise ValueError(f"Unbekannter Matcher '{name}'. Erlaubt: {', '.join(matchers)}.")
    return matchers[name]()