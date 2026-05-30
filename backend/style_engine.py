"""
Style Engine — Fingerprint + Learned Style generation for Beat Maker.

Hybrid approach:
  - Heuristic statistics (rhyme density, syllable metrics, lexical profile, structure)
  - Optional LLM pass (Ollama) for thematic/tone interpretation
  - Blended by a user-controlled bias slider (0.0 = pure heuristic, 1.0 = pure LLM)

All functions are pure and side-effect free, so they're easy to test.
"""
from __future__ import annotations

import re
import json
import math
from collections import Counter
from typing import Dict, List, Any, Optional

try:
    import pyphen
    _hyphen = pyphen.Pyphen(lang='en_US')
except Exception:
    _hyphen = None

_WORD_RE = re.compile(r"[A-Za-z']+")
_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'is', 'am', 'are', 'was', 'were', 'be',
    'been', 'being', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by', 'from',
    'it', 'its', "it's", 'i', "i'm", 'my', 'me', 'you', "you're", 'your', 'we',
    "we're", 'us', 'our', 'they', "they're", 'their', 'he', 'she', 'him', 'her',
    'his', 'hers', 'that', 'this', 'these', 'those', 'as', 'so', 'if', 'then',
    'than', 'not', "don't", "can't", "won't", 'just', 'like', 'yeah', 'gonna',
    'got', 'get', 'do', 'does', 'did', 'have', 'has', 'had', 'will', 'would',
    'could', 'should', 'can', 'no', 'yes', 'up', 'down', 'out', 'into', 'over',
    'some', 'any', 'all', 'now', 'when', 'where', 'who', 'what', 'why', 'how',
}


def _count_syllables(word: str) -> int:
    """Syllable count for a single word using pyphen if available, else a vowel-group heuristic."""
    w = word.lower().strip("'")
    if not w:
        return 0
    if _hyphen:
        parts = _hyphen.inserted(w).split('-')
        n = len([p for p in parts if p])
        return max(1, n)
    # Fallback: vowel-group count
    vowels = 'aeiouy'
    prev_v = False
    n = 0
    for ch in w:
        is_v = ch in vowels
        if is_v and not prev_v:
            n += 1
        prev_v = is_v
    if w.endswith('e') and n > 1:
        n -= 1
    return max(1, n)


def _strip_structure_markers(text: str) -> str:
    """Remove [Intro], (Chorus), etc. bracketed section labels."""
    return re.sub(r"[\[\(][^\]\)]{1,40}[\]\)]", "", text)


def _get_lines(text: str) -> List[str]:
    text = _strip_structure_markers(text)
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and not ln.startswith('#')]


def _last_word(line: str) -> Optional[str]:
    words = _WORD_RE.findall(line.lower())
    return words[-1] if words else None


def _rhyme_key(word: str) -> str:
    """Crude rhyme fingerprint: last vowel cluster + trailing consonants."""
    if not word:
        return ''
    w = word.lower().rstrip("'")
    # Find last vowel run
    m = re.search(r"[aeiouy]+[^aeiouy]*$", w)
    return m.group(0) if m else w[-2:]


def heuristic_fingerprint(corpus: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute deterministic, explainable style metrics from a list of corpus items.
    corpus: [{text: str, ...}, ...]
    """
    all_lines: List[str] = []
    all_words: List[str] = []
    for item in corpus:
        text = item.get('text', '') or ''
        lines = _get_lines(text)
        all_lines.extend(lines)
        for ln in lines:
            all_words.extend(_WORD_RE.findall(ln.lower()))

    total_lines = len(all_lines)
    total_words = len(all_words)

    # Lexical profile
    non_stop = [w for w in all_words if w not in _STOPWORDS and len(w) > 2]
    top_words = Counter(non_stop).most_common(20)
    bigrams = Counter()
    for i in range(len(all_words) - 1):
        a, b = all_words[i], all_words[i + 1]
        if a not in _STOPWORDS and b not in _STOPWORDS:
            bigrams[(a, b)] += 1
    top_bigrams = [(f"{a} {b}", c) for (a, b), c in bigrams.most_common(10)]

    vocab_size = len(set(all_words))
    ttr = vocab_size / total_words if total_words else 0.0  # type-token ratio (richness)

    # Syllabic metrics per line
    syllables_per_line: List[int] = []
    for ln in all_lines:
        words = _WORD_RE.findall(ln)
        syllables_per_line.append(sum(_count_syllables(w) for w in words))

    avg_syll = (sum(syllables_per_line) / total_lines) if total_lines else 0.0
    var_syll = 0.0
    if total_lines > 1:
        m = avg_syll
        var_syll = math.sqrt(sum((s - m) ** 2 for s in syllables_per_line) / total_lines)

    # Rhyme density: fraction of lines whose ending rhymes with any nearby line (±3)
    rhyme_keys = [_rhyme_key(_last_word(ln) or '') for ln in all_lines]
    rhymed = 0
    for i, k in enumerate(rhyme_keys):
        if not k:
            continue
        neighbors = rhyme_keys[max(0, i - 3):i] + rhyme_keys[i + 1:i + 4]
        if k in neighbors:
            rhymed += 1
    rhyme_density = rhymed / total_lines if total_lines else 0.0

    # Line length metrics (chars)
    char_lens = [len(ln) for ln in all_lines]
    avg_line_chars = (sum(char_lens) / total_lines) if total_lines else 0.0

    return {
        'corpus_stats': {
            'items': len(corpus),
            'total_lines': total_lines,
            'total_words': total_words,
            'unique_words': vocab_size,
        },
        'lexical': {
            'top_words': [{'word': w, 'count': c} for w, c in top_words],
            'top_bigrams': [{'phrase': p, 'count': c} for p, c in top_bigrams],
            'type_token_ratio': round(ttr, 3),
        },
        'phonetic': {
            'avg_syllables_per_line': round(avg_syll, 2),
            'syllables_stddev': round(var_syll, 2),
            'rhyme_density': round(rhyme_density, 3),
        },
        'structural': {
            'avg_line_chars': round(avg_line_chars, 1),
            'total_lines': total_lines,
        },
    }


def select_representative_samples(corpus: List[Dict[str, Any]], n: int = 3) -> List[str]:
    """Pick up to n corpus items with the richest content (most lines)."""
    scored = []
    for item in corpus:
        lines = _get_lines(item.get('text', '') or '')
        if not lines:
            continue
        scored.append((len(lines), item.get('text', '')))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:n]]


def build_learned_style_prompt(
    user_prompt: str,
    fingerprint: Dict[str, Any],
    samples: List[str],
    llm_theme_summary: Optional[str] = None,
    bias: float = 0.5,
) -> str:
    """
    Compose the full prompt fed to Ollama.
    bias: 0.0 = heuristic-dominant, 1.0 = LLM-theme-dominant.
    """
    bias = max(0.0, min(1.0, bias))
    lex = fingerprint.get('lexical', {})
    phon = fingerprint.get('phonetic', {})
    struct = fingerprint.get('structural', {})

    top_words = ', '.join(w['word'] for w in lex.get('top_words', [])[:10]) or '—'
    top_bigrams = ', '.join(p['phrase'] for p in lex.get('top_bigrams', [])[:5]) or '—'

    heuristic_block = f"""### Artist Fingerprint (measured)
- Signature vocabulary: {top_words}
- Recurring phrases: {top_bigrams}
- Average syllables per bar: {phon.get('avg_syllables_per_line', '—')} (±{phon.get('syllables_stddev', 0)})
- Rhyme density: {round((phon.get('rhyme_density', 0) or 0) * 100, 1)}% of lines rhyme with a nearby line
- Average line length: {struct.get('avg_line_chars', '—')} characters
- Vocabulary richness (type/token ratio): {lex.get('type_token_ratio', '—')}
"""

    theme_block = ''
    if llm_theme_summary:
        theme_block = f"""### Artist Voice (interpreted)
{llm_theme_summary.strip()}
"""

    samples_block = ''
    if samples:
        snippets = '\n\n---\n\n'.join(s.strip()[:600] for s in samples)
        samples_block = f"""### Representative samples from the artist's corpus
{snippets}
"""

    # Emphasis cue encodes the bias into the generation instructions
    if bias < 0.33:
        emphasis = "Match the MEASURED metrics above (syllable count, rhyme density, vocabulary) very closely. The interpreted voice is secondary."
    elif bias > 0.66:
        emphasis = "Prioritize the artist's VOICE and themes above. Treat the measured metrics as loose guidance."
    else:
        emphasis = "Balance measured metrics and interpreted voice equally."

    return f"""You are ghostwriting for a specific artist. Study their fingerprint below and write in their voice.

{heuristic_block}
{theme_block}
{samples_block}
### Direction emphasis
{emphasis}

### User's creative brief
{user_prompt}

Write 16-32 bars. Output ONLY the lyrics — no headings, no explanations.
"""
