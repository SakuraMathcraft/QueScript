import warnings
import numpy as np
import pandas as pd
from scipy import stats


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
    def calculate_kmo(df):
        work = df.apply(pd.to_numeric, errors="coerce")
        work = work.dropna(axis=1, how="all")
        if work.shape[1] < 2:
            return float("nan")

        # Remove constant items; KMO is undefined for zero-variance columns.
        variances = work.var(axis=0, ddof=1)
        work = work.loc[:, variances > 1e-12]
        if work.shape[1] < 2:
            return float("nan")

        corr_matrix = work.corr().fillna(0.0).values
        if corr_matrix.shape[0] < 2:
            return float("nan")

        # Mild ridge regularization stabilizes inverse on small n / many items.
        reg = 1e-3
        corr_reg = (1.0 - reg) * corr_matrix + reg * np.eye(corr_matrix.shape[0])

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
        if not np.isfinite(kmo):
            return float("nan")
        return float(np.clip(kmo, 0.0, 1.0))

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
        n, p = df.shape
        if n <= 1 or p <= 1:
            return 0.0, 1.0
        corr = df.corr().values
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
    def run_efa_suite(df, n_factors=None):
        corr = df.corr().fillna(0.0)
        eigvals, eigvecs = np.linalg.eigh(corr.values)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        suggested = int(np.sum(eigvals > 1.0))
        if n_factors is None:
            n_factors = max(1, suggested)
        n_factors = int(min(max(1, n_factors), df.shape[1]))

        loadings = eigvecs[:, :n_factors] @ np.diag(np.sqrt(np.maximum(eigvals[:n_factors], 0)))
        rotated = StatAnalyzer._varimax(loadings) if n_factors > 1 else loadings

        ss_loadings = np.sum(rotated**2, axis=0)
        explained_ratio = ss_loadings / df.shape[1]
        cum_ratio = np.cumsum(explained_ratio)

        loadings_df = pd.DataFrame(
            rotated,
            index=df.columns,
            columns=[f"Factor{i+1}" for i in range(n_factors)],
        )

        return {
            "kmo": float(StatAnalyzer.calculate_kmo(df)),
            "bartlett_chi2": StatAnalyzer.calculate_bartlett_sphericity(df)[0],
            "bartlett_p": StatAnalyzer.calculate_bartlett_sphericity(df)[1],
            "eigenvalues": [float(v) for v in eigvals],
            "suggested_factors": suggested,
            "n_factors_used": n_factors,
            "factor_loadings": loadings_df,
            "variance_explained": [float(v) for v in explained_ratio],
            "variance_cumulative": [float(v) for v in cum_ratio],
        }

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

        # Rank-based discretization preserves marginal spread and avoids degenerate bins.
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
