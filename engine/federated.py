"""DP aggregate SIMULATOR (not federated learning). Privacy unit = one organisation. Each org holds a local
Care Map and releases only a clipped rule-support vector; the aggregator adds Laplace noise.
release = sum_i clip_L1(v_i, C) + Lap(C / eps) per coordinate. Care Maps themselves never leave the org."""
import numpy as np


def clip_l1(v: np.ndarray, C: float) -> np.ndarray:
    n = np.abs(v).sum()
    return v if n <= C else v * (C / n)


def simulate(n_orgs=8, n_rules=12, C=4.0, eps=1.0, seed=0, suppress=1.0):
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.05, 0.9, n_rules)
    local = (rng.random((n_orgs, n_rules)) < true_p).astype(float)  # which rules each org has learned
    agg = sum(clip_l1(v, C) for v in local)
    noisy = agg + rng.laplace(0, C / eps, n_rules)
    noisy = np.where(noisy < suppress, 0.0, noisy)   # suppress tiny/rare rule counts
    return {"true": agg.tolist(), "released": noisy.tolist(), "mae": float(np.abs(noisy - agg).mean()), "eps": eps}


def sweep(epsilons=(0.1, 0.5, 1, 2, 5, 10), trials=40, **kw):
    out = []
    for e in epsilons:
        maes = [simulate(eps=e, seed=s, **kw)["mae"] for s in range(trials)]
        out.append({"eps": e, "mae": round(float(np.mean(maes)), 3)})
    return out
