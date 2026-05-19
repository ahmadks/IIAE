def deviation_score(response: str, axioms: list) -> float:
    """
    Minimal SDK heuristic for deviation score.
    Detects:
    - literal preservation
    - contextual negation
    - contradiction amplification (to match DQEReal behavior)
    """
    if not axioms:
        return 0.0

    import re
    # Split response into sentence/clause segments for localized verification
    resp_segments = [s.strip() for s in re.split(r'\.|\band\b|\bbut\b', response.lower()) if s.strip()]
    negations = {"no", "not", "forbidden", "disabled", "unnecessary", "irrelevant", "never"}

    matched = 0.0
    contradiction = False

    for ax in axioms:
        ax_words = set(ax.lower().replace(".", "").replace(",", "").split())
        
        # Find the response segment with the best word overlap for this axiom
        best_segment_words = set()
        best_overlap = -1
        
        for seg in resp_segments:
            seg_words = set(seg.replace(",", "").split())
            intersection = ax_words.intersection(seg_words)
            if len(intersection) > best_overlap:
                best_overlap = len(intersection)
                best_segment_words = seg_words
                
        # If no overlapping segment found, use the full response words as fallback
        if not best_segment_words:
            best_segment_words = set(response.lower().replace(".", "").replace(",", "").split())
            
        intersection = ax_words.intersection(best_segment_words)

        # Detect negation only within the best-matching segment (prevent cross-clause leaks)
        negated = any(
            (w in best_segment_words and any((n in best_segment_words and n not in ax_words) for n in negations))
            for w in ax_words
        )

        if negated:
            contradiction = True
            matched += 0.0
        elif len(ax_words) > 0 and len(intersection) / len(ax_words) >= 0.6:
            matched += 1.0
        else:
            matched += 0.0

    preservation = matched / len(axioms)

    # DQEReal-compatible deviation score
    ds = (1.0 - preservation) + (1.0 if contradiction else 0.0)
    return min(1.0, max(0.0, ds))

def classify_ds(ds: float) -> str:
    """
    Classify the deviation score into base types.
    """
    if ds == 0.0:
        return "Standard-Zero"
    elif ds <= 0.4:
        return "Tolerable"
    elif ds <= 0.8:
        return "Violation"
    else:
        return "Critical"
