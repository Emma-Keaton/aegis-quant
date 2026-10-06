"""Model evaluation: discrimination, calibration, information coefficients.

Pure numpy/scipy implementations — no sklearn dependency — used by the
promotion gate (IC, AUC) and the scoreboard.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> Optional[float]:
    """Mann-Whitney U formulation of ROC-AUC. None when only one class present."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    if len(s) != len(y) or len(s) < 2:
        return None
    pos = s[y == 1]
    neg = s[y == 0]
    n_pos, n_neg = len(pos), len(neg)
    if n_pos == 0 or n_neg == 0:
        return None
    # Average ranks with ties handled via mid-rank.
    combined = np.concatenate([pos, neg])
    order = combined.argsort()
    ranks = np.empty(len(combined), dtype=float)
    sorted_vals = combined[order]
    i = 0
    while i < len(sorted_vals):
        j = i
        while j + 1 < len(sorted_vals) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        mid_rank = (i + j) / 2.0 + 1.0  # 1-based mid-rank
        ranks[order[i:j + 1]] = mid_rank
        i = j + 1
    rank_sum_pos = float(ranks[:n_pos].sum())
    auc = (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(min(1.0, max(0.0, auc)))


def log_loss(probabilities: Sequence[float], labels: Sequence[int],
             eps: float = 1e-15) -> float:
    """Binary log loss; probabilities clipped to [eps, 1-eps]."""
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(labels, dtype=float)
    if len(p) == 0 or len(p) != len(y):
        return float("nan")
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def spearman_ic(predicted: Sequence[float], realized: Sequence[float]) -> Optional[float]:
    """Spearman rank information coefficient. None on insufficient data."""
    a = np.asarray(predicted, dtype=float)
    b = np.asarray(realized, dtype=float)
    if len(a) != len(b) or len(a) < 3:
        return None
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return None
    a, b = a[mask], b[mask]
    ra = _rankdata(a)
    rb = _rankdata(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return None
    ic = float(np.corrcoef(ra, rb)[0, 1])
    return ic if math.isfinite(ic) else None


def _rankdata(values: np.ndarray) -> np.ndarray:
    order = values.argsort()
    ranks = np.empty(len(values), dtype=float)
    sorted_vals = values[order]
    i = 0
    while i < len(sorted_vals):
        j = i
        while j + 1 < len(sorted_vals) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        mid_rank = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = mid_rank
        i = j + 1
    return ranks


def walk_forward_splits(n: int, n_splits: int = 5, embargo: int = 0) -> List[Tuple[int, int, int, int]]:
    """Anchored expanding-window splits: train [0,i), test [i,j).

    Returns list of (train_start, train_end, test_start, test_end) index pairs
    over `n` samples with `n_splits` test folds. The final fold ends at `n`.
    Embargo bars are skipped between train end and test start when embargo > 0;
    with embargo=0 the train and test windows are adjacent but non-overlapping.
    """
    if n < 20 or n_splits < 2:
        return []
    fold_size = n // n_splits
    splits: List[Tuple[int, int, int, int]] = []
    for k in range(n_splits - 1, -1, -1):
        test_end = n - k * fold_size
        test_start = test_end - fold_size
        train_end = max(2, test_start - embargo)
        if train_end < 2 or test_start < train_end or test_end <= test_start:
            continue
        splits.append((0, train_end, test_start, test_end))
    return list(reversed(splits))


def classification_report(scores: Sequence[float], labels: Sequence[int]) -> Dict[str, Optional[float]]:
    """AUC + log-loss + accuracy-at-0.5 in one call."""
    auc = roc_auc(scores, labels)
    ll = log_loss([_sigmoid(s) for s in scores], labels) if len(scores) else None
    preds = [1 if s > 0 else 0 for s in scores] if scores else []
    acc = (sum(1 for p, y in zip(preds, labels) if p == y) / len(preds)) if preds else None
    return {"roc_auc": auc, "log_loss": ll, "accuracy": acc, "n": len(labels)}


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(x, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(x, -60.0))
    return z / (1.0 + z)
