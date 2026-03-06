import os
import random
import time
import math
import json
import hashlib
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

try:
    from statistical_core import StatAnalyzer
except ImportError:
    # Use dummy if unavailable
    class StatAnalyzer:
        @staticmethod
        def generate_correlated_data(n, m, r, v, n_factors=1, random_state=None):
            return None

class SurveySimulator:
    def __init__(self, html_path, headless=True, speed_factor=1.0):
        self.html_path = html_path
        self.headless = headless
        self.speed_factor = speed_factor # 1.0 is normal, 0.5 is slower, 2.0 is faster (wait less)
        self.collected_data = [] # Store all responses
        self.scale_questions_map = [] # To map generated data columns to questions
        self.last_run_meta = {}

    def _resolve_chromium_executable(self):
        explicit = os.environ.get("QUESCRIPT_CHROMIUM_EXECUTABLE", "").strip()
        if explicit and os.path.exists(explicit):
            return explicit

        # Fallbacks for dev/build layouts.
        candidates = [
            os.path.join(os.getcwd(), "ms-playwright", "chrome-win64", "chrome.exe"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ms-playwright", "chrome-win64", "chrome.exe"),
        ]
        for path in candidates:
            norm = os.path.normpath(path)
            if os.path.exists(norm):
                return norm
        return None

    def _apply_bias(self, options, bias_type='random'):
        """
        Custom selection logic based on bias.
        options: list of elements or indices
        bias_type:
            'random': Pure random
            'positive': Skew towards end (higher values/satisfaction)
            'negative': Skew towards start (lower values/dissatisfaction)
            'central': Skew towards middle (normal distribution)
        """
        n = len(options)
        if n == 0: return None
        if n == 1: return options[0]

        indices = list(range(n))
        weights = [1] * n

        if bias_type == 'positive':
            # Linear increase weight
            weights = [i + 1 for i in indices]
        elif bias_type == 'negative':
            # Linear decrease weight
            weights = [n - i for i in indices]
        elif bias_type == 'central':
            # Bell curve approximation
            mid = (n - 1) / 2
            weights = [math.exp(-((i - mid) ** 2) / (2 * (n/4)**2)) for i in indices]

        # Select index based on weights
        chosen_idx = random.choices(indices, weights=weights, k=1)[0]
        return options[chosen_idx]

    def _build_question_index(self, page):
        questions = page.query_selector_all(".question")
        ordered_qids = []
        qid_to_element = {}
        fallback = []
        for idx, q in enumerate(questions, 1):
            qid = q.get_attribute("data-qid") or q.get_attribute("id") or str(idx)
            if qid.startswith("q") and qid[1:].isdigit():
                qid = qid[1:]
            fallback.append((idx, qid, q))
        # Sort by numeric qid when possible; fallback to dom order.
        numeric_items = [(int(qid), q) for _, qid, q in fallback if str(qid).isdigit()]
        if len(numeric_items) == len(fallback):
            numeric_items.sort(key=lambda x: x[0])
            for qid_int, q in numeric_items:
                qid = str(qid_int)
                ordered_qids.append(qid)
                qid_to_element[qid] = q
        else:
            for idx, _, q in fallback:
                qid = str(idx)
                ordered_qids.append(qid)
                qid_to_element[qid] = q
        return ordered_qids, qid_to_element

    def _resolve_next_qid(self, ordered_qids, current_qid, jump_target):
        if jump_target and jump_target in ordered_qids:
            return jump_target
        try:
            i = ordered_qids.index(current_qid)
        except ValueError:
            return None
        return ordered_qids[i + 1] if i + 1 < len(ordered_qids) else None

    def _build_repro_signature(self, payload):
        stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()

    def _save_audit_files(self, config_payload, path_logs):
        import pandas as pd

        out_dir = os.path.dirname(self.html_path)
        config_path = os.path.join(out_dir, "config.json")
        path_log_path = os.path.join(out_dir, "path_log.csv")

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_payload, f, ensure_ascii=False, indent=2)

        pd.DataFrame(path_logs).to_csv(path_log_path, index=False, encoding="utf-8-sig")

    def run_batch(
        self,
        count,
        bias='random',
        reliability='medium',
        validity='medium',
        progress_callback=None,
        stop_event=None,
        latent_dims=2,
        run_id=None,
        seed=None,
    ):
        """
        Run simulation for 'count' times.
        reliability/validity: Used for generating correlated data for scale/matrix questions.
        """
        file_url = f"file:///{self.html_path.replace(os.sep, '/')}"

        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if seed is None:
            seed = random.SystemRandom().randint(1, 2**31 - 1)
        random.seed(seed)

        config_payload = {
            "run_id": run_id,
            "seed": int(seed),
            "html_path": self.html_path,
            "count": int(count),
            "bias": bias,
            "reliability": reliability,
            "validity": validity,
            "latent_dims": int(latent_dims),
            "headless": bool(self.headless),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }

        # Reset data
        self.collected_data = []
        path_logs = []

        with sync_playwright() as p:
            launch_args = {"headless": self.headless}
            chromium_exe = self._resolve_chromium_executable()
            if chromium_exe:
                launch_args["executable_path"] = chromium_exe
            browser = p.chromium.launch(**launch_args)

            # --- Phase 1: Analyze Structure & Generate Data ---
            context = browser.new_context()
            page = context.new_page()
            page.goto(file_url)

            questions = page.query_selector_all(".question")
            scale_indices = []

            for idx, q in enumerate(questions):
                q_type = q.get_attribute("data-type")
                if q_type == "scale_radio":
                    scale_indices.append((idx, 'scale'))
                elif q_type == "matrix":
                    rows = q.query_selector_all("tbody tr")
                    for r_idx in range(len(rows)):
                        scale_indices.append((idx, f'matrix_row_{r_idx}'))

            n_scale_items = len(scale_indices)

            pre_generated_scales = None
            if n_scale_items > 0:
                try:
                    dims = 1 if n_scale_items < 3 else max(1, min(int(latent_dims), n_scale_items // 2 or 1))
                    df_scales = StatAnalyzer.generate_correlated_data(
                        count,
                        n_scale_items,
                        reliability,
                        validity,
                        n_factors=dims,
                        random_state=seed,
                    )
                    if df_scales is not None:
                        pre_generated_scales = df_scales.values
                except Exception as e:
                    print(f"Failed to generate statistical data: {e}")

            context.close()

            # --- Phase 2: Execution Loop ---

            for i in range(count):
                if stop_event and stop_event.is_set():
                    print("Simulation stopped by user.")
                    break

                context = browser.new_context()
                page = context.new_page()

                current_scale_row = pre_generated_scales[i] if pre_generated_scales is not None else None
                scale_cursor = 0

                try:
                    if not os.path.exists(self.html_path):
                        raise FileNotFoundError(f"HTML file not found: {self.html_path}")

                    try:
                        page.goto(file_url, timeout=10000)
                    except Exception as goto_err:
                        print(f"Navigation failed for iteration {i}: {goto_err}")
                        raise goto_err

                    session_response = {}
                    ordered_qids, qid_to_element = self._build_question_index(page)
                    current_qid = ordered_qids[0] if ordered_qids else None
                    visited_qids = []
                    jump_events = []

                    while current_qid:
                        q = qid_to_element.get(current_qid)
                        if q is None:
                            break

                        show_if_rule = self._parse_show_if(q)
                        if not self._is_question_visible_by_rule(show_if_rule, session_response):
                            src = show_if_rule.get("source_qid", "-") if show_if_rule else "-"
                            jump_events.append(f"semantic skip Q{current_qid} by show_if(source=Q{src})")
                            current_qid = self._resolve_next_qid(ordered_qids, current_qid, "")
                            continue

                        q_type = q.get_attribute("data-type")
                        val = None
                        jump_target = ""

                        if q_type == "radio":
                            radios = q.query_selector_all("input[type='radio']")
                            if radios:
                                choice = self._apply_bias(radios, bias)
                                if choice:
                                    choice.check()
                                    val = choice.get_attribute("value")
                                    jump_target = choice.get_attribute("data-jump-target") or ""

                        elif q_type == "checkbox":
                            checkboxes = q.query_selector_all("input[type='checkbox']")
                            if checkboxes:
                                k = random.randint(1, len(checkboxes))
                                choices = random.sample(checkboxes, k)
                                vals = []
                                for c in choices:
                                    c.check()
                                    vals.append(c.get_attribute("value"))
                                    if not jump_target:
                                        jump_target = c.get_attribute("data-jump-target") or ""
                                val = ";".join(vals)

                        elif q_type == "text":
                            textarea = q.query_selector("textarea")
                            if textarea:
                                txt = "模拟自动填写的文本回答。"
                                textarea.fill(txt)
                                val = txt

                        elif q_type == "sort":
                            inputs = q.query_selector_all("input[type='number']")
                            if inputs:
                                ranks = list(range(1, len(inputs) + 1))
                                random.shuffle(ranks)
                                vals = []
                                for idx, inp in enumerate(inputs):
                                    inp.fill(str(ranks[idx]))
                                    vals.append(str(ranks[idx]))
                                val = ",".join(vals)

                        elif q_type == "scale_radio":
                            radios = q.query_selector_all("input[type='radio']")
                            if radios:
                                if current_scale_row is not None and scale_cursor < len(current_scale_row):
                                    target_val = int(current_scale_row[scale_cursor])
                                    scale_cursor += 1
                                    pick_idx = min(max(target_val - 1, 0), len(radios) - 1)
                                    radios[pick_idx].check()
                                    val = radios[pick_idx].get_attribute("value")
                                else:
                                    choice = self._apply_bias(radios, bias)
                                    if choice:
                                        choice.check()
                                        val = choice.get_attribute("value")

                        elif q_type == "matrix":
                            rows = q.query_selector_all("tbody tr")
                            row_vals = []
                            for row in rows:
                                radios = row.query_selector_all("input[type='radio']")
                                if not radios:
                                    continue
                                if current_scale_row is not None and scale_cursor < len(current_scale_row):
                                    target_val = int(current_scale_row[scale_cursor])
                                    scale_cursor += 1
                                    pick_idx = min(max(target_val - 1, 0), len(radios) - 1)
                                    radios[pick_idx].check()
                                    sub_val = radios[pick_idx].get_attribute("value")
                                else:
                                    choice = self._apply_bias(radios, bias)
                                    if choice:
                                        choice.check()
                                        sub_val = choice.get_attribute("value")
                                    else:
                                        sub_val = ""
                                row_vals.append(sub_val)
                            val = "|".join(row_vals)

                        session_response[f"Q{current_qid}"] = val
                        visited_qids.append(current_qid)

                        next_qid = self._resolve_next_qid(ordered_qids, current_qid, jump_target)
                        jump_reason = "sequential"
                        if jump_target and jump_target in ordered_qids:
                            answer_val = "" if val is None else str(val)
                            jump_reason = f"jump by Q{current_qid} answer={answer_val} -> Q{jump_target}"
                            jump_events.append(jump_reason)

                        current_qid = next_qid

                    session_response["_run_id"] = run_id
                    session_response["_seed"] = seed
                    session_response["_sample_id"] = i + 1
                    self.collected_data.append(session_response)

                    path_logs.append(
                        {
                            "run_id": run_id,
                            "sample_id": i + 1,
                            "visited_questions": ">".join(visited_qids),
                            "jump_reasons": " | ".join(jump_events) if jump_events else "none",
                            "answer_count": len(visited_qids),
                            "status": "ok",
                        }
                    )
                    print(f"Iteration {i+1}/{count}: Data collected. ({len(session_response)} answers)")

                    page.on("dialog", lambda d: d.accept())
                    submit_btn = page.query_selector("#submitBtn")
                    if submit_btn:
                        submit_btn.click()
                        page.wait_for_timeout(300)

                    if progress_callback:
                        progress_callback(i + 1, count, "完成")

                except Exception as e:
                    print(f"Error in iteration {i+1}: {e}")
                    path_logs.append(
                        {
                            "run_id": run_id,
                            "sample_id": i + 1,
                            "visited_questions": "",
                            "jump_reasons": f"error: {e}",
                            "answer_count": 0,
                            "status": "error",
                        }
                    )
                    if progress_callback:
                        progress_callback(i + 1, count, f"错误: {str(e)}")
                finally:
                    context.close()

            browser.close()

        config_payload["completed_samples"] = len(self.collected_data)
        config_payload["stopped"] = bool(stop_event and stop_event.is_set())
        config_payload["ended_at"] = datetime.now().isoformat(timespec="seconds")
        config_payload["repro_signature"] = self._build_repro_signature(config_payload)
        self.last_run_meta = config_payload

        try:
            self._save_data_to_csv()
            self._save_audit_files(config_payload, path_logs)
        except Exception as e:
            print(f"Error saving data: {e}")

    def _save_data_to_csv(self):
        import pandas as pd
        out_path = os.path.join(os.path.dirname(self.html_path), "survey_data_collected.csv")

        if not self.collected_data:
            print("No data collected to save.")
            # Ensure file exists even if empty to avoid "File not found" error in GUI
            with open(out_path, 'w') as f: f.write("")
            return

        df = pd.DataFrame(self.collected_data)
        df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"Data saved to {out_path}")

    def _fill_page(self, page, bias):
        # Legacy method kept but not used in new run_batch logic logic to avoid huge refactor if simple fill is needed
        # Identify all question containers
        questions = page.query_selector_all(".question")

        # Base wait time logic
        base_wait = 0.5 / self.speed_factor

        for q in questions:
            q_type = q.get_attribute("data-type")

            if q_type == "radio":
                radios = q.query_selector_all("input[type='radio']")
                if radios:
                    choice = self._apply_bias(radios, bias)
                    if choice: choice.check()

            elif q_type == "checkbox":
                checkboxes = q.query_selector_all("input[type='checkbox']")
                if checkboxes:
                    # Determine how many to check
                    # For bias, maybe positive implies more checks? Let's keep count random for now
                    # but selection biased
                    k = random.randint(1, len(checkboxes))
                    # Apply weighted selection k times (without replacement if possible)
                    # For simplicity, just use random sample for checkboxes or complex logic
                    # Let's keep checkboxes random for MVP as bias usually applies to scale/radio
                    choices = random.sample(checkboxes, k)
                    for c in choices:
                        c.check()

            elif q_type == "text":
                textarea = q.query_selector("textarea")
                if textarea:
                    textarea.fill("模拟自动填写的文本回答。")

            elif q_type == "sort":
                inputs = q.query_selector_all("input[type='number']")
                if inputs:
                    ranks = list(range(1, len(inputs) + 1))
                    random.shuffle(ranks)
                    for idx, inp in enumerate(inputs):
                        inp.fill(str(ranks[idx]))

            elif q_type == "scale_radio":
                radios = q.query_selector_all("input[type='radio']")
                if radios:
                    # Scales are highly sensitive to bias (1-5 or 1-10)
                    choice = self._apply_bias(radios, bias)
                    if choice: choice.check()

            elif q_type == "matrix":
                rows = q.query_selector_all("tbody tr")
                for row in rows:
                    radios = row.query_selector_all("input[type='radio']")
                    if radios:
                        choice = self._apply_bias(radios, bias)
                        if choice: choice.check()

            # Simulate human delay if not purely instant
            if base_wait > 0.1:
                time.sleep(base_wait * random.uniform(0.5, 1.5))

    def _parse_show_if(self, question_el):
        raw = question_el.get_attribute("data-show-if")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _is_question_visible_by_rule(self, rule, session_response):
        if not rule:
            return True
        src_qid = str(rule.get("source_qid", "")).strip()
        if not src_qid:
            return True

        src_answer = session_response.get(f"Q{src_qid}")
        if src_answer is None:
            return False

        allowed = [str(v).strip() for v in (rule.get("allowed_values") or [])]
        if not allowed:
            return True

        raw = str(src_answer)
        values = [v.strip() for v in re.split(r"[;|,]", raw) if v.strip()]
        if not values:
            values = [raw.strip()]

        return any(v in allowed for v in values)
