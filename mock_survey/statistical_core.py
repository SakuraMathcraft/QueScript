import warnings
import logging
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar


class StatAnalyzer:
    @staticmethod
    def calculate_cronbach_alpha(df):
        item_scores = df
        n_items = df.shape[1]
        if n_items < 2:
            return 0.0
        item_variances = item_scores.var(axis=0, ddof=1)
        total_score_var = item_scores.sum(axis=1).var(ddof=1)
        if total_score_var == 0:
            return 0.0
        return (n_items / (n_items - 1)) * (1 - (item_variances.sum() / total_score_var))

    @staticmethod
    def _to_numeric_df(df):
        work = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        if work.empty:
            return work
        # Drop constant items to avoid singular correlation matrices.
        variances = work.var(axis=0, ddof=1)
        return work.loc[:, variances > 1e-12]

    @staticmethod
    def _regularize_corr(corr, ridge=1e-3):
        c = np.array(corr, dtype=float)
        c = np.nan_to_num(c, nan=0.0)
        np.fill_diagonal(c, 1.0)
        return (1.0 - ridge) * c + ridge * np.eye(c.shape[0])

    @staticmethod
    def _estimate_thresholds_from_ordinal(x):
        vals, counts = np.unique(x, return_counts=True)
        probs = counts / counts.sum()
        cum = np.cumsum(probs)[:-1]
        if len(cum) == 0:
            return np.array([-np.inf, np.inf]), vals
        cuts = stats.norm.ppf(np.clip(cum, 1e-6, 1 - 1e-6))
        thresholds = np.concatenate(([-np.inf], cuts, [np.inf]))
        return thresholds, vals

    @staticmethod
    def _bvn_rect_prob(tx0, tx1, ty0, ty1, rho):
        rv = stats.multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]], allow_singular=True)

        def cdf(x, y):
            if np.isneginf(x) or np.isneginf(y):
                return 0.0
            if np.isposinf(x) and np.isposinf(y):
                return 1.0
            if np.isposinf(x):
                return float(stats.norm.cdf(y))
            if np.isposinf(y):
                return float(stats.norm.cdf(x))
            return float(rv.cdf([x, y]))

        p = cdf(tx1, ty1) - cdf(tx0, ty1) - cdf(tx1, ty0) + cdf(tx0, ty0)
        return max(p, 1e-12)

    @staticmethod
    def _estimate_polychoric_pair(x, y):
        x = np.asarray(x)
        y = np.asarray(y)
        mask = np.isfinite(x) & np.isfinite(y)
        x = x[mask]
        y = y[mask]
        if len(x) < 10:
            return float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else 0.0

        tx, xvals = StatAnalyzer._estimate_thresholds_from_ordinal(x)
        ty, yvals = StatAnalyzer._estimate_thresholds_from_ordinal(y)

        x_map = {v: i for i, v in enumerate(xvals)}
        y_map = {v: i for i, v in enumerate(yvals)}
        table = np.zeros((len(xvals), len(yvals)), dtype=float)
        for xv, yv in zip(x, y):
            table[x_map[xv], y_map[yv]] += 1.0

        if np.count_nonzero(table) <= 1:
            return 0.0

        def nll(rho):
            ll = 0.0
            for i in range(len(xvals)):
                for j in range(len(yvals)):
                    c = table[i, j]
                    if c <= 0:
                        continue
                    p = StatAnalyzer._bvn_rect_prob(tx[i], tx[i + 1], ty[j], ty[j + 1], rho)
                    ll -= c * np.log(p)
            return ll

        try:
            res = minimize_scalar(nll, bounds=(-0.95, 0.95), method="bounded", options={"xatol": 1e-3})
            return float(np.clip(res.x, -0.999, 0.999)) if res.success else float(stats.spearmanr(x, y).statistic)
        except Exception:
            return float(stats.spearmanr(x, y).statistic)

    @staticmethod
    def compute_polychoric_matrix(df):
        work = StatAnalyzer._to_numeric_df(df)
        p = work.shape[1]
        if p < 2:
            return np.eye(max(p, 1)), list(work.columns), "polychoric"

        arr = work.values
        corr = np.eye(p, dtype=float)
        for i in range(p):
            for j in range(i + 1, p):
                corr_ij = StatAnalyzer._estimate_polychoric_pair(arr[:, i], arr[:, j])
                if not np.isfinite(corr_ij):
                    corr_ij = 0.0
                corr[i, j] = corr[j, i] = float(np.clip(corr_ij, -0.999, 0.999))

        corr = StatAnalyzer._regularize_corr(corr, ridge=1e-3)
        return corr, list(work.columns), "polychoric"

    @staticmethod
    def _build_corr_matrix(df, corr_method="auto"):
        work = StatAnalyzer._to_numeric_df(df)
        if work.shape[1] < 2:
            return np.eye(max(work.shape[1], 1)), list(work.columns), "pearson"

        method = (corr_method or "auto").lower()
        if method == "polychoric" or method == "auto":
            unique_levels = work.nunique(dropna=True)
            is_likert_like = bool((unique_levels <= 11).all())
            if method == "polychoric" or is_likert_like:
                try:
                    return StatAnalyzer.compute_polychoric_matrix(work)
                except Exception:
                    if method == "polychoric":
                        # explicit request should still return usable matrix
                        pass

        if method == "spearman":
            corr = work.corr(method="spearman").fillna(0.0).values
            return StatAnalyzer._regularize_corr(corr), list(work.columns), "spearman"

        corr = work.corr(method="pearson").fillna(0.0).values
        return StatAnalyzer._regularize_corr(corr), list(work.columns), "pearson"

    @staticmethod
    def calculate_kmo(df):
        corr_matrix, _, _ = StatAnalyzer._build_corr_matrix(df, corr_method="pearson")
        return StatAnalyzer.calculate_kmo_from_corr(corr_matrix)

    @staticmethod
    def calculate_kmo_from_corr(corr_matrix):
        corr_reg = StatAnalyzer._regularize_corr(corr_matrix)
        if corr_reg.shape[0] < 2:
            return float("nan")

        try:
            cond = np.linalg.cond(corr_reg)
        except np.linalg.LinAlgError:
            return float("nan")

        if not np.isfinite(cond) or cond > 1e8:
            return float("nan")

        try:
            inv_corr_matrix = np.linalg.inv(corr_reg)
        except np.linalg.LinAlgError:
            inv_corr_matrix = np.linalg.pinv(corr_reg)

        rows = corr_reg.shape[0]
        partial_corr = np.zeros((rows, rows))
        for i in range(rows):
            for j in range(rows):
                denom = np.sqrt(max(inv_corr_matrix[i, i] * inv_corr_matrix[j, j], 1e-12))
                partial_corr[i, j] = -inv_corr_matrix[i, j] / denom

        sum_sq_corr = np.sum(corr_reg**2) - np.sum(np.diag(corr_reg**2))
        sum_sq_partial = np.sum(partial_corr**2) - np.sum(np.diag(partial_corr**2))
        denom = sum_sq_corr + sum_sq_partial
        if denom <= 1e-12 or not np.isfinite(denom):
            return float("nan")

        kmo = float(sum_sq_corr / denom)
        return float(np.clip(kmo, 0.0, 1.0)) if np.isfinite(kmo) else float("nan")

    @staticmethod
    def calculate_discrimination(df):
        work_df = df.copy()
        work_df['Total'] = work_df.sum(axis=1)
        df_sorted = work_df.sort_values(by='Total', ascending=False)

        n = len(work_df)
        top_27 = int(n * 0.27)
        low_27 = int(n * 0.27)
        if top_27 == 0 or low_27 == 0:
            return {}

        high_group = df_sorted.head(top_27).drop(columns=['Total'])
        low_group = df_sorted.tail(low_27).drop(columns=['Total'])

        results = {}
        for col in high_group.columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                t_stat, p_val = stats.ttest_ind(high_group[col], low_group[col], equal_var=False)
            if np.isnan(t_stat) or np.isnan(p_val):
                t_stat, p_val = 0.0, 1.0
            results[col] = {'t': float(t_stat), 'p': float(p_val), 'significant': bool(p_val < 0.05)}
        return results

    @staticmethod
    def item_total_correlation(df):
        results = {}
        total = df.sum(axis=1)
        for col in df.columns:
            corrected_total = total - df[col]
            if corrected_total.var(ddof=1) == 0 or df[col].var(ddof=1) == 0:
                corr = 0.0
            else:
                corr = float(np.corrcoef(df[col], corrected_total)[0, 1])
                if np.isnan(corr):
                    corr = 0.0
            results[col] = corr
        return results

    @staticmethod
    def alpha_if_deleted(df):
        out = {}
        for col in df.columns:
            sub = df.drop(columns=[col])
            out[col] = 0.0 if sub.shape[1] < 2 else float(StatAnalyzer.calculate_cronbach_alpha(sub))
        return out

    @staticmethod
    def calculate_bartlett_sphericity(df):
        work = StatAnalyzer._to_numeric_df(df)
        return StatAnalyzer.calculate_bartlett_from_corr(work.corr().fillna(0.0).values, len(work))

    @staticmethod
    def calculate_bartlett_from_corr(corr, n_samples):
        p = corr.shape[0]
        n = int(n_samples)
        if n <= 1 or p <= 1:
            return 0.0, 1.0
        try:
            det_r = np.linalg.det(corr)
        except np.linalg.LinAlgError:
            det_r = 0.0
        det_r = max(float(det_r), 1e-12)
        chi2 = -(n - 1 - (2 * p + 5) / 6) * np.log(det_r)
        dof = p * (p - 1) / 2
        p_val = float(1 - stats.chi2.cdf(chi2, dof))
        return float(chi2), p_val

    @staticmethod
    def parallel_analysis(
        df,
        n_iter=200,
        percentile=95,
        random_state=None,
        corr_method="auto",
        corr_matrix=None,
        col_names=None,
    ):
        work = StatAnalyzer._to_numeric_df(df)

        if corr_matrix is None:
            corr, cols, corr_used = StatAnalyzer._build_corr_matrix(work, corr_method=corr_method)
        else:
            corr = StatAnalyzer._regularize_corr(corr_matrix)
            cols = list(col_names) if col_names else [f"V{i+1}" for i in range(corr.shape[0])]
            corr_used = (corr_method or "pearson").lower()

        p = corr.shape[0]
        n = len(work) if len(work) > 0 else max(50, p * 6)
        if p < 2:
            return {
                "suggested_factors": 1,
                "actual_eigenvalues": [1.0],
                "random_percentile_eigenvalues": [1.0],
                "corr_method_used": corr_used,
            }

        rng = np.random.default_rng(random_state)
        actual = np.linalg.eigvalsh(corr)[::-1]

        # Keep PA aligned with EFA correlation choice. For polychoric, use a stable
        # Spearman-based random criterion to avoid excessive per-iteration polychoric cost.
        pa_method = "spearman" if corr_used == "polychoric" else corr_used
        rand_eigs = np.zeros((n_iter, p), dtype=float)
        for i in range(n_iter):
            rnd = rng.standard_normal((n, p))
            if pa_method == "spearman":
                rc = pd.DataFrame(rnd).rank().corr(method="pearson").fillna(0.0).values
            else:
                rc = np.corrcoef(rnd, rowvar=False)
            rc = StatAnalyzer._regularize_corr(np.nan_to_num(rc, nan=0.0))
            rand_eigs[i, :] = np.linalg.eigvalsh(rc)[::-1]

        crit = np.percentile(rand_eigs, percentile, axis=0)
        suggested = int(np.sum(actual > crit))
        return {
            "suggested_factors": max(1, suggested),
            "actual_eigenvalues": [float(v) for v in actual],
            "random_percentile_eigenvalues": [float(v) for v in crit],
            "percentile": percentile,
            "iterations": n_iter,
            "corr_method_used": pa_method,
        }

    @staticmethod
    def velicer_map_test(df, corr_method="auto", corr_matrix=None, col_names=None):
        work = StatAnalyzer._to_numeric_df(df)

        if corr_matrix is None:
            r, cols, corr_used = StatAnalyzer._build_corr_matrix(work, corr_method=corr_method)
        else:
            r = StatAnalyzer._regularize_corr(corr_matrix)
            cols = list(col_names) if col_names else [f"V{i+1}" for i in range(r.shape[0])]
            corr_used = (corr_method or "pearson").lower()

        p = r.shape[0]
        if p < 2:
            return {"suggested_factors": 1, "map_values": [0.0], "corr_method_used": corr_used}

        eigvals, eigvecs = np.linalg.eigh(r)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        map_values = []
        for m in range(0, p):
            if m == 0:
                resid = r.copy()
            else:
                load = eigvecs[:, :m] @ np.diag(np.sqrt(np.maximum(eigvals[:m], 0)))
                reproduced = load @ load.T
                resid = r - reproduced
                np.fill_diagonal(resid, 1.0)

            off = resid - np.diag(np.diag(resid))
            map_values.append(float(np.mean(off**2)))

        suggested = int(np.argmin(map_values))
        return {
            "suggested_factors": max(1, suggested),
            "map_values": map_values,
            "corr_method_used": corr_used,
        }

    @staticmethod
    def scree_elbow(eigenvalues):
        vals = np.array(eigenvalues, dtype=float)
        if len(vals) <= 2:
            return 1
        d1 = np.diff(vals)
        d2 = np.diff(d1)
        # largest curvature index + 1 (factor count starts at 1)
        elbow = int(np.argmax(np.abs(d2)) + 1)
        return max(1, elbow)

    @staticmethod
    def calculate_omega(df):
        work = StatAnalyzer._to_numeric_df(df)
        if work.shape[1] < 2:
            return float("nan")
        corr = work.corr().fillna(0.0).values
        eigvals, eigvecs = np.linalg.eigh(corr)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        first_loading = eigvecs[:, 0] * np.sqrt(max(eigvals[0], 0.0))
        uniq = 1 - np.clip(first_loading**2, 0, 0.999)
        num = (np.sum(first_loading)) ** 2
        den = num + np.sum(uniq)
        if den <= 1e-12:
            return float("nan")
        return float(np.clip(num / den, 0.0, 1.0))

    @staticmethod
    def run_cfa_validation(df, n_factors=1, dimension_groups=None):
        work = StatAnalyzer._to_numeric_df(df)
        if work.shape[1] < 3:
            return {"available": False, "reason": "题项不足", "near_pd_risk": False}

        try:
            import semopy  # optional dependency
        except Exception:
            return {"available": False, "reason": "semopy未安装，已跳过CFA", "near_pd_risk": False}

        model_desc = ""

        # Preferred path: theory/branch-aware dimensions provided by caller.
        if dimension_groups:
            lines = []
            for dim, cols in dimension_groups.items():
                keep = [c for c in cols if c in work.columns]
                if len(keep) >= 3:
                    lines.append(f"{dim} =~ " + " + ".join(keep))
            if lines:
                model_desc = "\n".join(lines)
            else:
                return {"available": False, "reason": "理论维度题项不足(每维至少3题)"}
        else:
            # Fallback: exploratory assignment from EFA dominant loadings.
            efa = StatAnalyzer.run_efa_suite(work, n_factors=n_factors, corr_method="pearson")
            load_df = efa["factor_loadings"].abs()
            assign = load_df.idxmax(axis=1)

            lines = []
            for f in sorted(assign.unique()):
                items = assign[assign == f].index.tolist()
                if len(items) >= 2:
                    lines.append(f"{f} =~ " + " + ".join(items))

            if not lines:
                return {"available": False, "reason": "无法构建可识别CFA模型"}
            model_desc = "\n".join(lines)

        try:
            cov = work.cov().fillna(0.0).values
            eig_min = float(np.min(np.linalg.eigvalsh(cov))) if cov.size else float("nan")
            near_pd_risk = bool(np.isfinite(eig_min) and eig_min <= 1e-10)
        except Exception:
            eig_min = float("nan")
            near_pd_risk = False

        root_logger = logging.getLogger()
        old_level = root_logger.level
        try:
            # semopy may warn for non-PD covariance; keep console clean and expose flag in result.
            root_logger.setLevel(logging.ERROR)
            model = semopy.Model(model_desc)
            model.fit(work)
            fit = semopy.calc_stats(model)
            return {
                "available": True,
                "model": model_desc,
                "cfi": float(fit.get("CFI", np.nan).iloc[0]),
                "tli": float(fit.get("TLI", np.nan).iloc[0]),
                "rmsea": float(fit.get("RMSEA", np.nan).iloc[0]),
                "srmr": float(fit.get("SRMR", np.nan).iloc[0]) if "SRMR" in fit else float("nan"),
                "near_pd_risk": near_pd_risk,
                "cov_eig_min": eig_min,
            }
        except Exception as e:
            return {
                "available": False,
                "reason": f"CFA拟合失败: {e}",
                "near_pd_risk": near_pd_risk,
                "cov_eig_min": eig_min,
            }
        finally:
            root_logger.setLevel(old_level)

    @staticmethod
    def run_efa_suite(df, n_factors=None, corr_method="auto", pa_iter=200):
        work = StatAnalyzer._to_numeric_df(df)
        corr, col_names, corr_used = StatAnalyzer._build_corr_matrix(work, corr_method=corr_method)
        eigvals, eigvecs = np.linalg.eigh(corr)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        suggested_kaiser = int(np.sum(eigvals > 1.0))
        pa = StatAnalyzer.parallel_analysis(
            work,
            n_iter=pa_iter,
            corr_method=corr_used,
            corr_matrix=corr,
            col_names=col_names,
        )
        map_res = StatAnalyzer.velicer_map_test(
            work,
            corr_method=corr_used,
            corr_matrix=corr,
            col_names=col_names,
        )
        scree_k = StatAnalyzer.scree_elbow(eigvals)

        suggested = max(1, min(pa["suggested_factors"], len(col_names)))
        if n_factors is None:
            # PA is primary; MAP/Scree are auxiliary diagnostics.
            n_factors = suggested
            n_factors = max(1, min(n_factors, len(col_names)))
        n_factors = int(min(max(1, n_factors), len(col_names)))

        loadings = eigvecs[:, :n_factors] @ np.diag(np.sqrt(np.maximum(eigvals[:n_factors], 0)))
        rotated = StatAnalyzer._varimax(loadings) if n_factors > 1 else loadings

        ss_loadings = np.sum(rotated**2, axis=0)
        explained_ratio = ss_loadings / max(len(col_names), 1)
        cum_ratio = np.cumsum(explained_ratio)

        loadings_df = pd.DataFrame(
            rotated,
            index=col_names,
            columns=[f"Factor{i+1}" for i in range(n_factors)],
        )

        bart_chi2, bart_p = StatAnalyzer.calculate_bartlett_from_corr(corr, len(work))
        omega = StatAnalyzer.calculate_omega(work)

        return {
            "corr_method_used": corr_used,
            "kmo": float(StatAnalyzer.calculate_kmo_from_corr(corr)),
            "bartlett_chi2": bart_chi2,
            "bartlett_p": bart_p,
            "eigenvalues": [float(v) for v in eigvals],
            "suggested_factors": suggested,
            "suggested_factors_kaiser": int(max(1, suggested_kaiser)),
            "parallel_analysis": pa,
            "map_test": map_res,
            "scree_elbow": scree_k,
            "n_factors_used": n_factors,
            "factor_loadings": loadings_df,
            "variance_explained": [float(v) for v in explained_ratio],
            "variance_cumulative": [float(v) for v in cum_ratio],
            "omega_total": omega,
        }

    @staticmethod
    def _varimax(Phi, gamma=1.0, q=20, tol=1e-6):
        p, k = Phi.shape
        R = np.eye(k)
        d_old = 0
        for _ in range(q):
            Lambda = Phi @ R
            u, s, vh = np.linalg.svd(
                Phi.T @ (Lambda**3 - (gamma / p) * Lambda @ np.diag(np.diag(Lambda.T @ Lambda))),
                full_matrices=False,
            )
            R = u @ vh
            d = np.sum(s)
            if d_old != 0 and d / d_old < 1 + tol:
                break
            d_old = d
        return Phi @ R

    @staticmethod
    def generate_correlated_data(
        n_samples,
        n_items,
        reliability='medium',
        validity='medium',
        n_factors=1,
        random_state=None,
    ):
        rng = np.random.default_rng(random_state)
        n_factors = max(1, int(min(n_factors, n_items)))

        if reliability == 'high':
            primary_loading = 0.82
            noise_std = 0.35
        elif reliability == 'medium':
            primary_loading = 0.62
            noise_std = 0.60
        else:
            primary_loading = 0.42
            noise_std = 0.95

        if validity == 'high':
            cross_loading = 0.08
            latent_corr = 0.35
        elif validity == 'medium':
            cross_loading = 0.18
            latent_corr = 0.25
        else:
            cross_loading = 0.30
            latent_corr = 0.15

        cov = np.full((n_factors, n_factors), latent_corr)
        np.fill_diagonal(cov, 1.0)
        latent = rng.multivariate_normal(np.zeros(n_factors), cov, size=n_samples)

        loadings = np.zeros((n_items, n_factors))
        for i in range(n_items):
            main_factor = i % n_factors
            loadings[i, main_factor] = max(0.15, primary_loading + rng.uniform(-0.08, 0.08))
            for f in range(n_factors):
                if f != main_factor:
                    loadings[i, f] = rng.uniform(0.0, cross_loading)

        raw = latent @ loadings.T + rng.normal(0, noise_std, size=(n_samples, n_items))

        likert = np.zeros_like(raw, dtype=int)
        qs = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        for j in range(n_items):
            edges = np.quantile(raw[:, j], qs)
            edges = np.unique(edges)
            if len(edges) < 3:
                likert[:, j] = rng.integers(1, 6, size=n_samples)
                continue
            binned = np.digitize(raw[:, j], edges[1:-1], right=True) + 1
            likert[:, j] = np.clip(binned, 1, 5)

        return pd.DataFrame(likert, columns=[f'Q{i+1}' for i in range(n_items)])
