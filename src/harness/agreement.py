"""Agreement between two sets of yes/no labels on the same items: the four counts,
sensitivity and specificity of the second against the first, raw agreement, and Cohen's κ
with its standard-error interval. Used for the judge against your labels."""
from __future__ import annotations

import math


def four_counts(reference: dict[str, str], judged: dict[str, str], positive: str = "no") -> dict:
    """positive = the failure label ("no": the answer is not grounded). Returns the counts and the rates."""
    ids = [i for i in reference if i in judged and reference[i] in ("yes", "no") and judged[i] in ("yes", "no")]
    tp = sum(1 for i in ids if reference[i] == positive and judged[i] == positive)
    fn = sum(1 for i in ids if reference[i] == positive and judged[i] != positive)
    fp = sum(1 for i in ids if reference[i] != positive and judged[i] == positive)
    tn = sum(1 for i in ids if reference[i] != positive and judged[i] != positive)
    n = len(ids)
    out = {"n": n, "both_fail": tp, "missed": fn, "false_alarm": fp, "both_pass": tn,
           "sensitivity": tp / (tp + fn) if tp + fn else None, "specificity": tn / (tn + fp) if tn + fp else None,
           "agreement": (tp + tn) / n if n else None}
    if n:
        po = (tp + tn) / n
        p_ref = (tp + fn) / n; p_jud = (tp + fp) / n
        pe = p_ref * p_jud + (1 - p_ref) * (1 - p_jud)
        kappa = (po - pe) / (1 - pe) if pe < 1 else None
        se = math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if (pe < 1 and n) else None
        out.update({"kappa": kappa, "kappa_low": max(-1.0, kappa - 1.96 * se) if (kappa is not None and se) else None,
                    "kappa_high": min(1.0, kappa + 1.96 * se) if (kappa is not None and se) else None})
    return out


def corrected_rate(reported: float, sensitivity: float, specificity: float) -> float | None:
    """Rogan–Gladen: reported = sens·p + (1 − spec)(1 − p), solved for p."""
    denom = sensitivity - (1 - specificity)
    if denom <= 0:
        return None
    return max(0.0, min(1.0, (reported - (1 - specificity)) / denom))
