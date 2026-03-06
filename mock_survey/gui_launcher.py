import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import threading
import os
import sys
import json
import random
import hashlib
import math
import re
from datetime import datetime

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

survey_generator = None
SurveySimulator = None

try:
    import survey_generator
    from simulation_core import SurveySimulator
except ImportError as e:
    import tkinter.messagebox as msgbox
    try:
        msgbox.showerror("Error", f"Failed to import modules: {e}")
    except Exception:
        print(f"Failed to import modules: {e}")
    sys.exit(1)


class SurveyApp:
    MIN_SAMPLE = 30
    MIN_SCALE_ITEMS = 3
    MAX_LATENT_DIMS = 8
    DEFAULT_ANALYSIS_SCOPE = "coverage"
    DEFAULT_COVERAGE_THRESHOLD = 0.6
    MIN_BRANCH_SAMPLE_DEFAULT = 10
    MIN_BRANCH_ITEMS_DEFAULT = 3
    SCROLLBAR_WIDTH = 12
    LOG_PANEL_DEFAULT_WIDTH = 200
    LOG_PANEL_MIN_WIDTH = 100

    def __init__(self, root):
        self.root = root
        self.root.title("自动化问卷模拟系统 v1.0")
        self.root.geometry("1400x960")

        self.style = ttk.Style(theme="cosmo")
        self.phase_var = ttk.StringVar(value="待机")
        self.status_var = ttk.StringVar(value="准备就绪")
        self.overall_grade_var = ttk.StringVar(value="目标达成评级: -")
        self.rel_target_var = ttk.StringVar(value="信度目标一致性: -")
        self.val_target_var = ttk.StringVar(value="效度目标一致性: -")
        self.struct_risk_var = ttk.StringVar(value="结构风险评级: -")

        self.stop_event = threading.Event()
        self.is_running = False
        self.current_run_meta = {}
        self.analysis_scope_var = ttk.StringVar(value=self.DEFAULT_ANALYSIS_SCOPE)
        self.coverage_threshold_var = ttk.DoubleVar(value=self.DEFAULT_COVERAGE_THRESHOLD)
        self.branch_min_sample_var = ttk.IntVar(value=self.MIN_BRANCH_SAMPLE_DEFAULT)
        self.branch_min_items_var = ttk.IntVar(value=self.MIN_BRANCH_ITEMS_DEFAULT)
        self.scope_help_var = ttk.StringVar()

        main_frame = ttk.Frame(root, padding=14)
        main_frame.pack(fill=BOTH, expand=YES)

        header = ttk.Frame(main_frame)
        header.pack(fill=X, pady=(0, 12))
        ttk.Label(header, text="问卷模拟大师", font=("Helvetica", 20, "bold"), bootstyle="primary").pack(side=LEFT)
        ttk.Label(header, text="v1.0", font=("Helvetica", 10), bootstyle="secondary").pack(side=LEFT, padx=8, pady=(6, 0))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=YES, fill=BOTH)

        self.tab_gen = ttk.Frame(self.notebook, padding=16)
        self.tab_sim = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.tab_gen, text="1. 问卷生成")
        self.notebook.add(self.tab_sim, text="2. 智能模拟")

        self._init_gen_tab()
        self._init_sim_tab()
        # Bottom status bar removed to avoid clipped text on some DPI/layout combinations.

    def _default_html_path(self):
        cwd = os.getcwd()
        if os.path.basename(cwd) == "mock_survey":
            return os.path.join(cwd, "index.html")
        return os.path.join(cwd, "mock_survey", "index.html")

    def _runtime_mock_survey_dir(self):
        # In packaged mode we write under LocalAppData; in source mode use repo mock_survey.
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            app_dir = os.path.join(local_app_data, "QueScriptSurvey", "mock_survey")
            try:
                os.makedirs(app_dir, exist_ok=True)
                return app_dir
            except Exception:
                pass

        script_dir = os.path.dirname(os.path.abspath(__file__))
        return script_dir if os.path.basename(script_dir) == "mock_survey" else os.path.join(script_dir, "mock_survey")

    def _dialog_initialdir(self, preferred_path=""):
        candidates = []

        def _push(path_val):
            if not path_val:
                return
            path_val = os.path.abspath(path_val)
            if os.path.isdir(path_val):
                candidates.append(path_val)
            else:
                candidates.append(os.path.dirname(path_val))

        _push(preferred_path)
        if hasattr(self, "sim_html_var"):
            _push(self.sim_html_var.get())
        if hasattr(self, "html_out_var"):
            _push(self.html_out_var.get())

        candidates.append(self._runtime_mock_survey_dir())
        candidates.append(os.getcwd())

        for d in candidates:
            if d and os.path.isdir(d):
                return d
        return os.getcwd()

    def _init_gen_tab(self):
        ttk.Label(self.tab_gen, text="步骤1: 将文本问卷转化为网页", font=("Arial", 12, "bold")).pack(anchor=W, pady=(0, 15))
        ttk.Label(self.tab_gen, text="请选择包含问卷内容的文本文件 (.txt)，系统将自动生成可用于模拟的网页。", bootstyle="secondary").pack(anchor=W, pady=(0, 20))

        input_group = ttk.Labelframe(self.tab_gen, text="输入文件")
        input_group.pack(fill=X, pady=10, ipadx=15, ipady=5)
        ttk.Label(input_group, text="问卷文本文件 (.txt):").pack(anchor=W, padx=15, pady=(15, 0))
        in_row = ttk.Frame(input_group)
        in_row.pack(fill=X, pady=5, padx=15)

        self.txt_path_var = ttk.StringVar()
        ttk.Entry(in_row, textvariable=self.txt_path_var).pack(side=LEFT, expand=YES, fill=X, padx=(0, 5))
        ttk.Button(in_row, text="浏览", command=self.browse_txt, bootstyle="outline-primary").pack(side=RIGHT)

        output_group = ttk.Labelframe(self.tab_gen, text="输出配置")
        output_group.pack(fill=X, pady=10, ipadx=15, ipady=5)
        ttk.Label(output_group, text="输出网页文件 (.html):").pack(anchor=W, padx=15, pady=(15, 0))
        out_row = ttk.Frame(output_group)
        out_row.pack(fill=X, pady=5, padx=15)

        self.html_out_var = ttk.StringVar(value=self._default_html_path())
        ttk.Entry(out_row, textvariable=self.html_out_var).pack(side=LEFT, expand=YES, fill=X, padx=(0, 5))
        ttk.Button(out_row, text="浏览", command=self.browse_html_out, bootstyle="outline-primary").pack(side=RIGHT)

        self.btn_generate = ttk.Button(self.tab_gen, text="生成网页问卷", command=self.generate_survey, bootstyle="success", width=20)
        self.btn_generate.pack(pady=30)

    def _init_sim_tab(self):
        root_row = ttk.Frame(self.tab_sim)
        root_row.pack(fill=BOTH, expand=YES)

        split = ttk.Panedwindow(root_row, orient=HORIZONTAL)
        split.pack(fill=BOTH, expand=YES)

        left_host = ttk.Frame(split)
        right_panel = ttk.Labelframe(split, text="运行日志")
        right_panel.configure(width=max(1, int(self.LOG_PANEL_DEFAULT_WIDTH)))
        split.add(left_host, weight=10)
        split.add(right_panel, weight=1)
        # Left pane absorbs resize; right log pane keeps narrow baseline width.
        try:
            split.paneconfigure(left_host, weight=1)
            split.paneconfigure(right_panel, weight=0)
            split.paneconfigure(right_panel, minsize=max(1, int(self.LOG_PANEL_MIN_WIDTH)))
        except Exception:
            # Some ttk variants expose `pane` instead of `paneconfigure`.
            try:
                split.pane(left_host, weight=1)
                split.pane(right_panel, weight=0, minsize=max(1, int(self.LOG_PANEL_MIN_WIDTH)))
            except Exception:
                pass
        self.root.after_idle(lambda s=split: self._set_initial_split_width(s))
        self.root.after(180, lambda s=split: self._set_initial_split_width(s))

        left_canvas = tk.Canvas(left_host, highlightthickness=0, borderwidth=0)
        left_scroll = tk.Scrollbar(
            left_host,
            orient=VERTICAL,
            command=left_canvas.yview,
            width=self.SCROLLBAR_WIDTH,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        left_scroll.pack(side=RIGHT, fill=Y)

        left_panel = ttk.Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left_panel, anchor="nw")

        # Keep scroll region and content width synced with the canvas viewport.
        left_panel.bind("<Configure>", lambda _e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.bind("<Configure>", lambda e: left_canvas.itemconfigure(left_window, width=e.width))

        self._sim_scroll_canvas = left_canvas
        left_canvas.bind("<Enter>", lambda _e: left_canvas.bind_all("<MouseWheel>", self._on_sim_mousewheel))
        left_canvas.bind("<Leave>", lambda _e: left_canvas.unbind_all("<MouseWheel>"))

        ttk.Label(left_panel, text="步骤2: 批量自动填写", font=("Arial", 12, "bold")).pack(anchor=W, pady=(0, 15))

        grade_bar = ttk.Labelframe(left_panel, text="测量目标状态")
        grade_bar.pack(fill=X, pady=(0, 10), ipadx=10, ipady=8)
        grade_row = ttk.Frame(grade_bar)
        grade_row.pack(fill=X, padx=10, pady=6)

        self.grade_label = ttk.Label(grade_row, textvariable=self.overall_grade_var, font=("Arial", 12, "bold"), bootstyle="secondary")
        self.grade_label.pack(side=LEFT)
        ttk.Separator(grade_row, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=12)
        self.rel_level_label = ttk.Label(grade_row, textvariable=self.rel_target_var, bootstyle="secondary")
        self.rel_level_label.pack(side=LEFT)
        ttk.Label(grade_row, text=" | ", bootstyle="secondary").pack(side=LEFT)
        self.val_level_label = ttk.Label(grade_row, textvariable=self.val_target_var, bootstyle="secondary")
        self.val_level_label.pack(side=LEFT)
        ttk.Separator(grade_row, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=12)
        self.struct_level_label = ttk.Label(grade_row, textvariable=self.struct_risk_var, bootstyle="secondary")
        self.struct_level_label.pack(side=LEFT)

        ttk.Button(grade_row, text="回填上次参数", command=self.replay_from_config, bootstyle="outline-info", width=12).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(grade_row, text="打开审计目录", command=self.open_audit_folder, bootstyle="outline-secondary", width=12).pack(side=RIGHT)

        ttk.Label(
            grade_bar,
            text="复现入口: 运行后在目标 HTML 同目录读取 config.json 与 path_log.csv；可点“回填上次参数”一键载入。",
            bootstyle="secondary",
            font=("Arial", 9),
        ).pack(anchor=W, padx=10, pady=(0, 4))

        target_group = ttk.Labelframe(left_panel, text="目标设置")
        target_group.pack(fill=X, pady=10, ipadx=15, ipady=5)
        target_row = ttk.Frame(target_group)
        target_row.pack(fill=X, padx=15, pady=15)

        ttk.Label(target_row, text="目标网页 (.html):", width=15).pack(side=LEFT)
        self.sim_html_var = ttk.StringVar(value=self._default_html_path())
        ttk.Entry(target_row, textvariable=self.sim_html_var).pack(side=LEFT, expand=YES, fill=X, padx=5)
        ttk.Button(target_row, text="浏览", command=self.browse_html_in, bootstyle="outline-primary").pack(side=RIGHT)

        cfg_group = ttk.Labelframe(left_panel, text="模拟参数 (可控信效度)")
        cfg_group.pack(fill=X, pady=10, ipadx=15, ipady=5)
        container = ttk.Frame(cfg_group)
        container.pack(fill=X, padx=15, pady=15)

        row1 = ttk.Frame(container)
        row1.pack(fill=X, pady=5)
        ttk.Label(row1, text="模拟样本数量:", width=15).pack(side=LEFT)
        self.sim_count_var = ttk.IntVar(value=self.MIN_SAMPLE)
        ttk.Spinbox(row1, from_=self.MIN_SAMPLE, to=10000, textvariable=self.sim_count_var, width=10).pack(side=LEFT, padx=5)
        ttk.Label(
            row1,
            text=f"建议最小样本和最小题项: n>={self.MIN_SAMPLE} 且量表题>={self.MIN_SCALE_ITEMS}",
            bootstyle="warning",
            font=("Arial", 9),
        ).pack(side=LEFT, padx=(10, 0))


        row_scope = ttk.Frame(container)
        row_scope.pack(fill=X, pady=5)
        ttk.Label(row_scope, text="分析口径:", width=15).pack(side=LEFT)
        self.scope_combo = ttk.Combobox(row_scope, textvariable=self.analysis_scope_var, state="readonly", width=16)
        self.scope_combo["values"] = ("coverage", "strict_public")
        self.scope_combo.pack(side=LEFT, padx=5)

        ttk.Label(row_scope, text="覆盖率阈值:", width=12).pack(side=LEFT, padx=(12, 0))
        ttk.Spinbox(row_scope, from_=0.30, to=1.00, increment=0.05, textvariable=self.coverage_threshold_var, width=8).pack(side=LEFT, padx=5)

        ttk.Label(row_scope, text="分支最小样本:", width=12).pack(side=LEFT, padx=(12, 0))
        ttk.Spinbox(row_scope, from_=5, to=1000, textvariable=self.branch_min_sample_var, width=8).pack(side=LEFT, padx=5)

        ttk.Label(row_scope, text="分支最小题项:", width=12).pack(side=LEFT, padx=(12, 0))
        ttk.Spinbox(row_scope, from_=1, to=50, textvariable=self.branch_min_items_var, width=8).pack(side=LEFT, padx=5)

        ttk.Label(container, textvariable=self.scope_help_var, bootstyle="secondary", font=("Arial", 9), wraplength=760, justify=LEFT).pack(fill=X, padx=(120, 0), pady=(2, 6))

        row2 = ttk.Frame(container)
        row2.pack(fill=X, pady=5)
        ttk.Label(row2, text="信度目标(Alpha):", width=15).pack(side=LEFT)
        self.reliability_var = ttk.StringVar(value="medium")
        r_combo = ttk.Combobox(row2, textvariable=self.reliability_var, state="readonly", width=10)
        r_combo["values"] = ("high", "medium", "low")
        r_combo.pack(side=LEFT, padx=5)

        ttk.Label(row2, text="效度目标(KMO):", width=15).pack(side=LEFT, padx=(20, 0))
        self.validity_var = ttk.StringVar(value="medium")
        v_combo = ttk.Combobox(row2, textvariable=self.validity_var, state="readonly", width=10)
        v_combo["values"] = ("high", "medium", "low")
        v_combo.pack(side=LEFT, padx=5)

        ttk.Label(row2, text="潜变量维度:", width=12).pack(side=LEFT, padx=(20, 0))
        self.latent_dims_var = ttk.IntVar(value=2)
        self.dims_combo = ttk.Combobox(row2, textvariable=self.latent_dims_var, state="readonly", width=8)
        self.dims_combo["values"] = tuple(range(1, self.MAX_LATENT_DIMS + 1))
        self.dims_combo.pack(side=LEFT, padx=5)

        self.measurement_help_var = ttk.StringVar()
        self.measurement_help_label = ttk.Label(
            container,
            textvariable=self.measurement_help_var,
            bootstyle="secondary",
            font=("Arial", 9),
            wraplength=760,
            justify=LEFT,
        )
        self.measurement_help_label.pack(fill=X, padx=(120, 0), pady=(2, 6))
        r_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_measurement_help())
        v_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_measurement_help())
        self.dims_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_measurement_help())
        self.scope_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_scope_help())
        self._update_scope_help()
        self._refresh_latent_dim_options(self.sim_html_var.get())
        self._update_measurement_help()

        row3 = ttk.Frame(container)
        row3.pack(fill=X, pady=5)
        ttk.Label(row3, text="其他题型倾向:", width=15).pack(side=LEFT)
        self.bias_var = ttk.StringVar(value="random")
        self.bias_combo = ttk.Combobox(row3, textvariable=self.bias_var, state="readonly", width=15)
        self.bias_combo["values"] = ("random", "positive", "negative", "central")
        self.bias_combo.pack(side=LEFT, padx=5)
        ttk.Label(row3, text="(影响非量表题目的选择倾向)", bootstyle="secondary", font=("Arial", 8)).pack(side=LEFT, padx=5)

        self.bias_help_var = ttk.StringVar()
        self.bias_help_label = ttk.Label(container, textvariable=self.bias_help_var, bootstyle="secondary", font=("Arial", 9), wraplength=760, justify=LEFT)
        self.bias_help_label.pack(fill=X, padx=(120, 0), pady=(2, 6))
        self.bias_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_bias_help())
        self._update_bias_help()

        row4 = ttk.Frame(container)
        row4.pack(fill=X, pady=5)
        self.headless_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(row4, text="无头模式 (后台运行，速度极快)", variable=self.headless_var, bootstyle="round-toggle").pack(side=LEFT)

        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill=X, pady=(8, 4), ipadx=2, ipady=2)

        self.btn_start = tk.Button(
            action_frame,
            text="开始 Start",
            command=self.start_simulation,
            width=12,
            font=("Microsoft YaHei", 10, "bold"),
            bg="#2f7ed8",
            fg="white",
            activebackground="#2f7ed8",
            activeforeground="white",
            relief="raised",
            bd=1,
            padx=6,
            pady=5,
            cursor="hand2",
        )
        self.btn_start.pack(side=LEFT, padx=(0, 8), pady=2)
        self._bind_button_hover(self.btn_start)

        self.btn_stop = tk.Button(
            action_frame,
            text="停止 Stop",
            command=self.stop_simulation,
            width=10,
            font=("Microsoft YaHei", 10, "bold"),
            state="disabled",
            bg="#2f7ed8",
            fg="white",
            activebackground="#2f7ed8",
            activeforeground="white",
            disabledforeground="#d4e3f8",
            relief="raised",
            bd=1,
            padx=6,
            pady=5,
            cursor="arrow",
        )
        self.btn_stop.pack(side=LEFT, pady=2)
        self._bind_button_hover(self.btn_stop)

        phase_wrap = ttk.Frame(left_panel)
        phase_wrap.pack(fill=X, pady=(2, 2))
        ttk.Label(phase_wrap, text="当前阶段:", bootstyle="secondary").pack(side=LEFT)
        ttk.Label(phase_wrap, textvariable=self.phase_var, bootstyle="info").pack(side=LEFT, padx=8)
        ttk.Label(phase_wrap, text="状态:", bootstyle="secondary").pack(side=LEFT, padx=(16, 0))
        ttk.Label(phase_wrap, textvariable=self.status_var, bootstyle="secondary").pack(side=LEFT, padx=6)

        self.progress_var = ttk.DoubleVar()
        self.progress_bar = ttk.Progressbar(left_panel, variable=self.progress_var, maximum=100, bootstyle="striped-success", mode="determinate")
        self.progress_bar.pack(fill=X, pady=(1, 6))

        self.log_text = ttk.Text(right_panel, width=1, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill=BOTH, expand=YES, side=LEFT)
        scroll = tk.Scrollbar(
            right_panel,
            orient=VERTICAL,
            command=self.log_text.yview,
            width=self.SCROLLBAR_WIDTH,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)


    def _bind_button_hover(self, button):
        """Add cursor/click feedback for tk buttons without changing button color."""
        def _enabled():
            return str(button.cget("state")) != "disabled"

        def _on_enter(_event):
            if _enabled():
                button.configure(cursor="hand2")

        def _on_leave(_event):
            button.configure(cursor="hand2" if _enabled() else "arrow")
            button.configure(relief="raised")

        def _on_press(_event):
            if _enabled():
                button.configure(relief="sunken")

        def _on_release(_event):
            if _enabled():
                button.configure(relief="raised")

        button.bind("<Enter>", _on_enter)
        button.bind("<Leave>", _on_leave)
        button.bind("<ButtonPress-1>", _on_press)
        button.bind("<ButtonRelease-1>", _on_release)

    def _set_initial_split_width(self, split_widget):
        """Set a stable initial width for the log panel; subsequent resizing still uses pane weights."""
        try:
            self.root.update_idletasks()
            total_w = int(split_widget.winfo_width() or self.root.winfo_width() or 0)
            if total_w < 300:
                # Geometry is not ready yet; retry shortly.
                self.root.after(80, lambda s=split_widget: self._set_initial_split_width(s))
                return

            desired_log_w = max(int(self.LOG_PANEL_MIN_WIDTH), int(self.LOG_PANEL_DEFAULT_WIDTH))
            max_log_w = max(1, total_w - 260)
            desired_log_w = min(desired_log_w, max_log_w)
            sash_x = max(1, total_w - desired_log_w)

            try:
                split_widget.sashpos(0, sash_x)
            except Exception:
                # Fallback for environments where sashpos setter is not exposed.
                split_widget.tk.call(split_widget._w, "sashpos", 0, sash_x)
        except Exception:
            # Keep UI usable even if pane sizing is unsupported on a platform theme.
            return

    def _on_sim_mousewheel(self, event):
        if not hasattr(self, "_sim_scroll_canvas"):
            return
        # Scroll only when the simulation tab is active.
        try:
            if self.notebook.select() != str(self.tab_sim):
                return
        except Exception:
            pass
        delta = int(-1 * (event.delta / 120)) if event.delta else 0
        if delta:
            self._sim_scroll_canvas.yview_scroll(delta, "units")

    def _clear_log_views(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_measurement_help(self):
        rel = self.reliability_var.get()
        val = self.validity_var.get()
        dims = self.latent_dims_var.get()

        rel_desc = {
            "high": "high: 更强内部一致性（通常更容易得到较高Alpha）",
            "medium": "medium: 接近常规真实调查，推荐默认",
            "low": "low: 一致性较弱，适合压力测试或反例测试",
        }.get(rel, "")

        val_desc = {
            "high": "high: 因子结构更清晰（通常更利于KMO/EFA解释）",
            "medium": "medium: 中等结构清晰度，推荐默认",
            "low": "low: 结构更混杂，常用于鲁棒性测试",
        }.get(val, "")

        if dims == 1:
            dim_desc = "维度=1: 单潜变量，适合单一满意度/态度量表"
        elif dims == 2:
            dim_desc = "维度=2: 双潜变量，适合大多数市场调研（推荐）"
        else:
            dim_desc = f"维度={dims}: 多潜变量，建议每维至少3题，样本尽量>=100"

        tip = "首选组合: reliability=medium, validity=medium, 潜变量维度=2；若做EFA稳定性验证，建议增加样本量。"
        self.measurement_help_var.set(f"{rel_desc}；{val_desc}；{dim_desc}。{tip}")

    def _update_bias_help(self):
        desc = {
            "random": "random: 完全随机，最接近真实样本，推荐用于通用模拟。",
            "positive": "positive: 偏高/偏正向（更容易选后面或高分项），适合模拟口碑较好的场景。",
            "negative": "negative: 偏低/偏负向（更容易选前面或低分项），适合压力测试或差评场景。",
            "central": "central: 偏中间（更容易选中间选项），适合保守回答或中性样本。",
        }
        self.bias_help_var.set(desc.get(self.bias_var.get(), ""))

    def browse_txt(self):
        f = filedialog.askopenfilename(
            title="选择问卷文本文件",
            initialdir=self._dialog_initialdir(self.txt_path_var.get()),
            filetypes=[("Text Files", "*.txt")],
        )
        if f:
            self.txt_path_var.set(f)

    def browse_html_out(self):
        current = self.html_out_var.get().strip()
        f = filedialog.asksaveasfilename(
            title="选择网页问卷保存位置",
            initialdir=self._dialog_initialdir(current),
            initialfile=os.path.basename(current) if current else "index.html",
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html")],
        )
        if f:
            self.html_out_var.set(f)

    def browse_html_in(self):
        f = filedialog.askopenfilename(
            title="选择目标网页问卷",
            initialdir=self._dialog_initialdir(self.sim_html_var.get()),
            filetypes=[("HTML Files", "*.html")],
        )
        if f:
            self.sim_html_var.set(f)
            self._refresh_latent_dim_options(f)
            self._update_measurement_help()

    def generate_survey(self):
        txt_path = self.txt_path_var.get()
        html_path = self.html_out_var.get()

        if not os.path.exists(txt_path):
            messagebox.showerror("错误", "找不到输入的文本文件！")
            return

        self.status_var.set("正在生成问卷...")
        old_text = self.btn_generate.cget("text")
        self.btn_generate.configure(text="正在生成...", state="disabled")
        self.root.update()

        try:
            data = survey_generator.parse_survey(txt_path)
            if not data:
                raise ValueError("未解析到任何题目。请检查题干是否包含题型标记（如 [单选题]/[多选题]）以及文件编码。")
            title = survey_generator.extract_survey_title(txt_path)
            os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
            survey_generator.generate_html(data, html_path, survey_title=title)
            self.status_var.set(f"成功生成: {os.path.basename(html_path)}")
            self.sim_html_var.set(html_path)
            self._refresh_latent_dim_options(html_path)
            self._update_measurement_help()
            messagebox.showinfo("成功", "\u95ee\u5377\u7f51\u9875\u751f\u6210\u5b8c\u6bd5\uff01\n\u5df2\u81ea\u52a8\u586b\u5165\u6a21\u62df\u9875\u9762\uff0c\u8bf7\u5207\u6362\u5230 '智能模拟' \u6807\u7b7e\u9875\u5f00\u59cb\u8fd0\u884c\u3002")
            self.notebook.select(self.tab_sim)
        except Exception as e:
            self.status_var.set("生成失败")
            messagebox.showerror("生成失败", f"发生错误:\n{e}")
        finally:
            self.btn_generate.configure(text=old_text, state="normal")

    def _consistency_bootstyle(self, level):
        return {"达标": "success", "临界": "warning", "偏离": "danger"}.get(level, "secondary")

    def _eval_target_level(self, metric, target, value):
        metric = (metric or "").lower()
        target = (target or "").lower()
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return "-"

        if metric == "reliability":
            if target == "high":
                if value >= 0.80:
                    return "达标"
                if value >= 0.75:
                    return "临界"
                return "偏离"
            if target == "medium":
                if 0.70 <= value <= 0.90:
                    return "达标"
                if 0.65 <= value <= 0.95:
                    return "临界"
                return "偏离"
            if target == "low":
                if value < 0.70:
                    return "达标"
                if value < 0.75:
                    return "临界"
                return "偏离"
            return "-"

        if metric == "validity":
            if target == "high":
                if value >= 0.70:
                    return "达标"
                if value >= 0.60:
                    return "临界"
                return "偏离"
            if target == "medium":
                if value >= 0.60:
                    return "达标"
                if value >= 0.50:
                    return "临界"
                return "偏离"
            if target == "low":
                if value < 0.60:
                    return "达标"
                if value < 0.65:
                    return "临界"
                return "偏离"
            return "-"

        return "-"

    def _evaluate_target_consistency(self, alpha, kmo, target_rel, target_val):
        rel_level = self._eval_target_level("reliability", target_rel, alpha)
        val_level = self._eval_target_level("validity", target_val, kmo)

        levels = [x for x in (rel_level, val_level) if x in ("达标", "临界", "偏离")]
        if not levels:
            grade = "-"
        elif "偏离" in levels:
            grade = "C"
        elif "临界" in levels:
            grade = "B"
        else:
            grade = "A"

        return {
            "grade": grade,
            "reliability": rel_level,
            "validity": val_level,
        }

    def _evaluate_structural_risk(self, sample_n, item_n, item_true_scale, item_selected, kmo, cfa, branch_meta, settings):
        score = 0
        reasons = []

        if sample_n < 50:
            score += 2
            reasons.append(f"样本量偏小(n={sample_n})，结构指标稳定性较弱。")
        elif sample_n < 100:
            score += 1
            reasons.append(f"样本量中等(n={sample_n})，建议增样本提升稳定性。")

        if item_n < 6:
            score += 2
            reasons.append(f"当前全样本仅纳入{item_n}题，难代表整份量表结构。")
        elif item_n < 10:
            score += 1
            reasons.append(f"当前全样本纳入题项仅{item_n}题，维度识别能力有限。")

        if item_true_scale > 0:
            cov_ratio = item_selected / max(item_true_scale, 1)
            if cov_ratio < 0.50:
                score += 2
                reasons.append(f"全样本仅覆盖真量表题的{cov_ratio:.0%}，分支互斥较强。")
            elif cov_ratio < 0.80:
                score += 1
                reasons.append(f"全样本覆盖真量表题约{cov_ratio:.0%}，需结合分支结论解读。")

        if isinstance(kmo, (int, float)) and math.isfinite(kmo):
            if kmo < 0.50:
                score += 2
                reasons.append(f"KMO={kmo:.3f} 偏低，结构效度风险较高。")
            elif kmo < 0.70:
                score += 1
                reasons.append(f"KMO={kmo:.3f} 临界，结构效度仍需验证。")

        if cfa and cfa.get("available"):
            cfi = cfa.get("cfi", float("nan"))
            rmsea = cfa.get("rmsea", float("nan"))
            severe = (isinstance(cfi, (int, float)) and math.isfinite(float(cfi)) and cfi < 0.80) or (
                isinstance(rmsea, (int, float)) and math.isfinite(float(rmsea)) and rmsea > 0.12
            )
            mild = (isinstance(cfi, (int, float)) and math.isfinite(float(cfi)) and cfi < 0.90) or (
                isinstance(rmsea, (int, float)) and math.isfinite(float(rmsea)) and rmsea > 0.08
            )
            if severe:
                score += 2
                reasons.append(f"CFA拟合偏差较大(CFI={cfi:.3f}, RMSEA={rmsea:.3f})。")
            elif mild:
                score += 1
                reasons.append(f"CFA拟合未完全达阈值(CFI={cfi:.3f}, RMSEA={rmsea:.3f})。")

        stable_branches = [b for b in (branch_meta or []) if not b.get("excluded_from_overall", False)]
        exploratory_count = sum(1 for b in (branch_meta or []) if b.get("exploratory_only", False))
        if exploratory_count > 0:
            score += 1
            reasons.append(f"有{exploratory_count}个分支因 n/p<5 仅作探索性参考，不纳入总体结论。")

        if len(stable_branches) >= 2:
            items = [int(b.get("item_count", 0)) for b in stable_branches]
            gap = max(items) - min(items)
            if gap >= 10:
                score += 2
                reasons.append("可纳入总体的分支间题项覆盖差异很大。")
            elif gap >= 6:
                score += 1
                reasons.append("可纳入总体的分支间题项覆盖差异较大。")

        grade = "A" if score <= 2 else ("B" if score <= 5 else "C")
        return {"grade": grade, "score": int(score), "reasons": reasons}

    def _update_consistency_banner(self, result=None):
        if not result:
            self.overall_grade_var.set("目标达成评级: -")
            self.rel_target_var.set("信度目标一致性: -")
            self.val_target_var.set("效度目标一致性: -")
            self.struct_risk_var.set("结构风险评级: -")
            self.grade_label.configure(bootstyle="secondary")
            self.rel_level_label.configure(bootstyle="secondary")
            self.val_level_label.configure(bootstyle="secondary")
            self.struct_level_label.configure(bootstyle="secondary")
            return

        grade = result.get("grade", "-")
        rel = result.get("reliability", "-")
        val = result.get("validity", "-")
        struct_grade = result.get("structural_grade", "-")

        grade_style = {"A": "success", "B": "warning", "C": "danger"}.get(grade, "secondary")
        struct_style = {"A": "success", "B": "warning", "C": "danger"}.get(struct_grade, "secondary")
        self.overall_grade_var.set(f"目标达成评级: {grade}")
        self.rel_target_var.set(f"信度目标一致性: {rel}")
        self.val_target_var.set(f"效度目标一致性: {val}")
        self.struct_risk_var.set(f"结构风险评级: {struct_grade}")

        self.grade_label.configure(bootstyle=grade_style)
        self.rel_level_label.configure(bootstyle=self._consistency_bootstyle(rel))
        self.val_level_label.configure(bootstyle=self._consistency_bootstyle(val))
        self.struct_level_label.configure(bootstyle=struct_style)

    def replay_from_config(self):
        html_path = self.sim_html_var.get()
        if not html_path:
            messagebox.showwarning("提示", "请先选择目标 HTML。")
            return

        cfg, _ = self._load_audit_context(html_path)
        analysis_meta = self._load_analysis_meta(html_path)
        if not cfg and not analysis_meta:
            messagebox.showinfo("复现入口", "未找到 config.json 或 analysis_meta.json。请先运行一次模拟，或检查目标 HTML 同目录。")
            return

        try:
            count = int(cfg.get("count", self.MIN_SAMPLE)) if cfg else self.MIN_SAMPLE
            self.sim_count_var.set(max(self.MIN_SAMPLE, count))
            self.bias_var.set(str((cfg or {}).get("bias", self.bias_var.get())))
            self.reliability_var.set(str((cfg or {}).get("reliability", self.reliability_var.get())))
            self.validity_var.set(str((cfg or {}).get("validity", self.validity_var.get())))
            self.latent_dims_var.set(int((cfg or {}).get("latent_dims", self.latent_dims_var.get())))
            self.headless_var.set(bool((cfg or {}).get("headless", self.headless_var.get())))

            effective_analysis = dict((analysis_meta or {}).get("analysis_settings") or {})
            if cfg:
                for k in ("scope", "coverage_threshold", "branch_min_sample", "branch_min_items"):
                    if k in cfg:
                        effective_analysis[k] = cfg.get(k)

            if "scope" in effective_analysis:
                self.analysis_scope_var.set(str(effective_analysis.get("scope", self.analysis_scope_var.get())))
            if "coverage_threshold" in effective_analysis:
                self.coverage_threshold_var.set(float(effective_analysis.get("coverage_threshold", self.coverage_threshold_var.get())))
            if "branch_min_sample" in effective_analysis:
                self.branch_min_sample_var.set(int(effective_analysis.get("branch_min_sample", self.branch_min_sample_var.get())))
            if "branch_min_items" in effective_analysis:
                self.branch_min_items_var.set(int(effective_analysis.get("branch_min_items", self.branch_min_items_var.get())))

            self._update_measurement_help()
            self._update_bias_help()
            self._update_scope_help()
            self.log(f"已回填参数: run_id={(cfg or {}).get('run_id', '-')}, seed={(cfg or {}).get('seed', '-')}")
            messagebox.showinfo(
                "复现入口",
                "已回填上次运行参数。\n复现方式: 保持参数不变后再次点击“开始模拟”。\n可复现关键字段见报告中的“审计摘要”与 analysis_meta.json。",
            )
        except Exception as e:
            messagebox.showerror("复现入口", f"回填参数失败: {e}")

    def open_audit_folder(self):
        html_path = self.sim_html_var.get()
        folder = os.path.dirname(html_path) if html_path else ""
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "未找到目标目录。请先确认 HTML 路径。")
            return
        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror("错误", f"打开目录失败: {e}")

    def start_simulation(self):
        html_path = self.sim_html_var.get()
        if not os.path.exists(html_path):
            messagebox.showerror("错误", "找不到目标 HTML 文件！")
            return

        self._update_consistency_banner(None)

        try:
            count = self.sim_count_var.get()
        except Exception:
            messagebox.showerror("错误", "请输入有效的数量！")
            return

        if count < self.MIN_SAMPLE:
            self.sim_count_var.set(self.MIN_SAMPLE)
            messagebox.showwarning("样本量不足", f"模拟样本量不能低于 {self.MIN_SAMPLE}。已自动调整为 {self.MIN_SAMPLE}。")
            return

        bias = self.bias_var.get()
        reliability = self.reliability_var.get()
        validity = self.validity_var.get()
        latent_dims = self.latent_dims_var.get()
        headless = self.headless_var.get()

        run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        seed = random.SystemRandom().randint(1, 2**31 - 1)
        self.current_run_meta = {"run_id": run_id, "seed": seed}

        self.is_running = True
        self.stop_event.clear()
        self._set_run_state("running")
        self.progress_var.set(0)
        self.status_var.set("正在运行模拟...")
        self._clear_log_views()

        self.log("--- 任务启动 ---")
        self.log(f"目标文件: {os.path.basename(html_path)}")
        self.log(f"计划样本: {count} 份")
        self.log(f"信度: {reliability} / 效度: {validity}")
        self.log(f"潜变量维度: {latent_dims}")
        self.log(f"其他倾向: {bias}")
        self.log(f"运行模式: {'后台(Headless)' if headless else '前台(GUI)'}")
        self.log(f"运行标识 run_id: {run_id}")
        self.log(f"随机种子 seed: {seed}")

        t = threading.Thread(
            target=self._run_thread,
            args=(html_path, count, bias, reliability, validity, latent_dims, headless, run_id, seed),
            daemon=True,
        )
        t.start()

    def stop_simulation(self):
        if self.is_running:
            self.stop_event.set()
            self.status_var.set("正在停止...")
            self._set_run_state("stopping")
            self.log("正在请求停止...")

    def _run_thread(self, html_path, count, bias, reliability, validity, latent_dims, headless, run_id, seed):
        try:
            simulator = SurveySimulator(html_path, headless=headless)

            def callback(current, total, status):
                pct = (current / total) * 100
                self.root.after(0, lambda: self.progress_var.set(pct))
                self.root.after(0, lambda: self.phase_var.set(f"正在填写问卷... {int(pct)}%"))
                self.root.after(0, lambda: self.log(f"[{current}/{total}] {status}"))

            simulator.run_batch(
                count,
                bias=bias,
                reliability=reliability,
                validity=validity,
                latent_dims=latent_dims,
                run_id=run_id,
                seed=seed,
                progress_callback=callback,
                stop_event=self.stop_event,
            )
            self.current_run_meta.update(getattr(simulator, "last_run_meta", {}) or {})
            self.root.after(0, lambda: self.log("=== 模拟任务完成 ==="))
            self.root.after(0, lambda: self.status_var.set("正在分析结果..."))
            self.root.after(0, lambda: self._set_run_state("analyzing"))
            self.root.after(0, lambda: self._show_analysis_report(html_path))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"ERROR: {e}"))
            self.root.after(0, lambda: self.status_var.set("任务出错"))
            self.root.after(0, lambda: self._set_run_state("error"))
            self.root.after(0, lambda: messagebox.showerror("运行错误", str(e)))

    def _set_run_state(self, state):
        if state == "running":
            self.btn_start.configure(state="disabled", cursor="arrow")
            self.btn_stop.configure(state="normal", cursor="hand2")
            self.phase_var.set("正在填写问卷...")
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.stop()
        elif state == "stopping":
            self.btn_stop.configure(state="disabled", cursor="arrow")
            self.phase_var.set("正在停止...")
        elif state == "analyzing":
            self.btn_start.configure(state="disabled", cursor="arrow")
            self.btn_stop.configure(state="disabled", cursor="arrow")
            self.phase_var.set("正在分析问卷结果...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(12)
        elif state == "done":
            self.is_running = False
            self.btn_start.configure(state="normal", cursor="hand2")
            self.btn_stop.configure(state="disabled", cursor="arrow")
            self.phase_var.set("完成")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
        elif state == "error":
            self.is_running = False
            self.btn_start.configure(state="normal", cursor="hand2")
            self.btn_stop.configure(state="disabled", cursor="arrow")
            self.phase_var.set("异常")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")

    def _collect_scale_numeric(self, df_raw):
        import pandas as pd

        question_cols = [c for c in df_raw.columns if str(c).startswith("Q")]
        if not question_cols:
            return pd.DataFrame()

        expanded_parts = []
        for col in question_cols:
            s = df_raw[col]
            non_null = s.dropna().astype(str)
            if non_null.empty:
                continue
            if non_null.str.contains("|", regex=False).mean() >= 0.2:
                split_df = s.astype(str).str.split("|", expand=True, regex=False)
                split_df.columns = [f"{col}_r{i+1}" for i in range(split_df.shape[1])]
                expanded_parts.append(split_df)
            else:
                expanded_parts.append(pd.DataFrame({col: s}))

        if not expanded_parts:
            return pd.DataFrame()

        work = pd.concat(expanded_parts, axis=1)
        work = work.replace({"": None, "None": None, "nan": None})
        return work.apply(pd.to_numeric, errors="coerce")

    def _select_scale_items(self, numeric_df, scope="strict_public", coverage_threshold=0.6, impute=True):
        import pandas as pd

        if numeric_df is None or numeric_df.empty:
            return pd.DataFrame(), [], [], {}

        ratio = numeric_df.notna().mean()
        strict_items = ratio[ratio >= 0.999].index.tolist()

        if scope == "coverage":
            selected_items = ratio[ratio >= float(coverage_threshold)].index.tolist()
        else:
            selected_items = strict_items

        selected = numeric_df[selected_items].copy() if selected_items else pd.DataFrame(index=numeric_df.index)

        if impute and not selected.empty:
            for col in selected.columns:
                med = selected[col].median()
                if pd.notna(med):
                    fill_val = med
                else:
                    mode = selected[col].mode()
                    fill_val = mode.iloc[0] if not mode.empty else 3
                selected[col] = selected[col].fillna(fill_val)

        return selected, strict_items, selected_items, {str(k): float(v) for k, v in ratio.to_dict().items()}

    def _extract_scale_dataframe(self, df_raw, min_answer_ratio=0.3, require_all_answered=False, impute=True):
        # Backward-compatible wrapper used by older call sites.
        numeric = self._collect_scale_numeric(df_raw)
        scope = "strict_public" if require_all_answered else "coverage"
        threshold = 0.999 if require_all_answered else float(min_answer_ratio)
        selected, _, _, _ = self._select_scale_items(numeric, scope=scope, coverage_threshold=threshold, impute=impute)
        return selected

    def _get_analysis_settings(self):
        scope = str(self.analysis_scope_var.get() or self.DEFAULT_ANALYSIS_SCOPE).strip().lower()
        if scope not in ("strict_public", "coverage"):
            scope = self.DEFAULT_ANALYSIS_SCOPE

        try:
            coverage = float(self.coverage_threshold_var.get())
        except Exception:
            coverage = self.DEFAULT_COVERAGE_THRESHOLD
        coverage = max(0.30, min(1.00, coverage))

        try:
            branch_min_sample = int(self.branch_min_sample_var.get())
        except Exception:
            branch_min_sample = self.MIN_BRANCH_SAMPLE_DEFAULT
        branch_min_sample = max(1, branch_min_sample)

        try:
            branch_min_items = int(self.branch_min_items_var.get())
        except Exception:
            branch_min_items = self.MIN_BRANCH_ITEMS_DEFAULT
        branch_min_items = max(1, branch_min_items)

        return {
            "scope": scope,
            "coverage_threshold": coverage,
            "branch_min_sample": branch_min_sample,
            "branch_min_items": branch_min_items,
        }

    def _analysis_scope_label(self, settings):
        if (settings or {}).get("scope") == "coverage":
            return f"按覆盖率纳入(>= {settings.get('coverage_threshold', self.DEFAULT_COVERAGE_THRESHOLD):.2f})"
        return "严格公共题(100%覆盖)"

    def _update_scope_help(self):
        settings = self._get_analysis_settings()
        self.scope_help_var.set(
            f"全样本口径: {self._analysis_scope_label(settings)}；分支门槛: n>={settings['branch_min_sample']} 且题项>={settings['branch_min_items']}。"
        )

    def _load_analysis_meta(self, html_path):
        meta_path = os.path.join(os.path.dirname(html_path), "analysis_meta.json")
        if not os.path.exists(meta_path) or os.path.getsize(meta_path) == 0:
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_analysis_meta(self, html_path, payload):
        meta_path = os.path.join(os.path.dirname(html_path), "analysis_meta.json")
        data = dict(payload or {})
        data["generated_at"] = datetime.now().isoformat(timespec="seconds")
        sign_base = {k: v for k, v in data.items() if k != "analysis_signature"}
        data["analysis_signature"] = hashlib.sha256(
            json.dumps(sign_base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def _load_question_meta(self, html_path):
        meta = {}
        if not os.path.exists(html_path):
            return meta
        try:
            with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
        except Exception:
            return meta

        for m in re.finditer(r'<div class="question"[^>]*data-qid="(\d+)"[^>]*>', html):
            tag = m.group(0)
            qid = m.group(1)
            q_type = ""
            show_if_sig = "public"

            m_type = re.search(r'data-type="([^"]+)"', tag)
            if m_type:
                q_type = m_type.group(1)

            m_show = re.search(r"data-show-if='([^']+)'", tag)
            if m_show:
                try:
                    obj = json.loads(m_show.group(1))
                    src = str(obj.get("source_qid", ""))
                    vals = [str(v).strip() for v in (obj.get("allowed_values") or [])]
                    vals = sorted([v for v in vals if v])
                    if src and vals:
                        show_if_sig = f"Q{src}:{'|'.join(vals)}"
                except Exception:
                    pass

            meta[qid] = {"type": q_type, "show_if_sig": show_if_sig}

        return meta

    def _infer_theory_dimensions(self, columns, html_path):
        groups = {}
        meta = self._load_question_meta(html_path)

        for col in columns:
            name = str(col)
            base = name.split("_r")[0]
            qid = base[1:] if base.startswith("Q") else base

            if "_r" in name:
                key = f"D_matrix_{base}"
            else:
                sig = meta.get(qid, {}).get("show_if_sig", "public")
                key = f"D_{sig}"

            groups.setdefault(key, []).append(name)

        return {k: v for k, v in groups.items() if len(v) >= 3}

    def _load_audit_context(self, html_path):
        audit_dir = os.path.dirname(html_path)
        config_path = os.path.join(audit_dir, "config.json")
        path_log_path = os.path.join(audit_dir, "path_log.csv")

        cfg = {}
        path_df = None

        if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}

        if os.path.exists(path_log_path) and os.path.getsize(path_log_path) > 0:
            try:
                import pandas as pd
                path_df = pd.read_csv(path_log_path)
            except Exception:
                path_df = None

        return cfg, path_df

    def _build_audit_summary(self, html_path):
        cfg, path_df = self._load_audit_context(html_path)
        analysis_meta = self._load_analysis_meta(html_path)
        lines = ["\n【审计摘要】"]

        if cfg:
            key_params = {
                "run_id": cfg.get("run_id", "-"),
                "seed": cfg.get("seed", "-"),
                "count": cfg.get("count", "-"),
                "completed_samples": cfg.get("completed_samples", "-"),
                "bias": cfg.get("bias", "-"),
                "reliability": cfg.get("reliability", "-"),
                "validity": cfg.get("validity", "-"),
                "latent_dims": cfg.get("latent_dims", "-"),
                "headless": cfg.get("headless", "-"),
                "started_at": cfg.get("started_at", "-"),
                "ended_at": cfg.get("ended_at", "-"),
                "stopped": cfg.get("stopped", "-"),
            }
            cfg_for_sign = {k: v for k, v in cfg.items() if k != "repro_signature"}
            local_sig = hashlib.sha256(
                json.dumps(cfg_for_sign, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            lines.append(f"可复现签名: {cfg.get('repro_signature', local_sig)}")
            lines.append("关键参数: " + ", ".join([f"{k}={v}" for k, v in key_params.items()]))
        else:
            lines.append("未找到 config.json（无法显��运��签名与关键参数）。")

        if analysis_meta:
            scope_label = self._analysis_scope_label(analysis_meta.get("analysis_settings", {}))
            lines.append(f"分析复现签名: {analysis_meta.get('analysis_signature', '-')}")
            lines.append(f"分析口径: {scope_label}")
            lines.append(f"分支门槛: n>={analysis_meta.get('analysis_settings', {}).get('branch_min_sample', '-')}, 题项>={analysis_meta.get('analysis_settings', {}).get('branch_min_items', '-')}")

        if path_df is not None and not path_df.empty:
            lines.append(f"路径日志样本数: {len(path_df)}")
            jump_mask = path_df["jump_reasons"].astype(str).str.lower().ne("none") if "jump_reasons" in path_df.columns else None
            if jump_mask is not None:
                lines.append(f"触发跳题样本数: {int(jump_mask.sum())}")

            preview = path_df.head(3)
            lines.append("样本轨迹预览(前3条):")
            for _, row in preview.iterrows():
                sid = row.get("sample_id", "?")
                trace = row.get("visited_questions", "")
                reason = row.get("jump_reasons", "")
                lines.append(f"- sample#{sid}: trace={trace}; jumps={reason}")
        else:
            lines.append("未找到 path_log.csv（无法展示题目访问轨迹/跳转原因）。")

        return "\n".join(lines) + "\n"

    def _build_parameter_summary(self, html_path):
        cfg, _ = self._load_audit_context(html_path)
        if not cfg:
            return "【本次模拟设定】\n未找到配置文件，无法展示本次参数设定。\n\n"

        rel = str(cfg.get("reliability", "-")).lower()
        val = str(cfg.get("validity", "-")).lower()
        dims = cfg.get("latent_dims", "-")
        bias = cfg.get("bias", "-")
        n = cfg.get("count", "-")

        rel_map = {
            "high": "高信度目标（通常期望 Alpha >= 0.80）",
            "medium": "中信度目标（通常期望 Alpha 在 0.70~0.85）",
            "low": "低信度目标（用于压力测试）",
        }
        val_map = {
            "high": "高效度目标（通常期望 KMO 更高、EFA结构更清晰）",
            "medium": "中效度目标（接近常规真实样本）",
            "low": "低效度目标（用于鲁棒性测试）",
        }
        bias_map = {
            "random": "随机作答倾向（最接近常规抽样）",
            "positive": "偏正向倾向（更易选择高分/后位选项）",
            "negative": "偏负向倾向（更易选择低分/前位选项）",
            "central": "偏中间倾向（更易选择中间选项）",
        }

        txt = "【本次模拟设定】\n"
        txt += f"- 样本量设定: {n}\n"
        txt += f"- 信度设定: {cfg.get('reliability', '-')}（{rel_map.get(rel, '未定义')}）\n"
        txt += f"- 效度设定: {cfg.get('validity', '-')}（{val_map.get(val, '未定义')}）\n"
        txt += f"- 潜变量维度: {dims}（1=单维，2=双维，>=3=多维）\n"
        txt += f"- 其他题型倾向: {cfg.get('bias', '-')}（{bias_map.get(str(bias).lower(), '未定义')}）\n"
        txt += f"- 运行模式: {'后台(Headless)' if cfg.get('headless') else '前台(GUI)'}\n\n"
        return txt

    def _show_analysis_report(self, html_path):
        # Run heavy statistics in a worker thread; only UI updates return to main thread.
        threading.Thread(target=self._show_analysis_report_worker, args=(html_path,), daemon=True).start()

    def _show_analysis_report_worker(self, html_path):
        try:
            csv_path = os.path.join(os.path.dirname(html_path), "survey_data_collected.csv")
            if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
                self.root.after(0, lambda: messagebox.showinfo("分析报告", "未采集到有效数据，请检查模拟过程。"))
                self.root.after(0, lambda: self._set_run_state("done"))
                return

            import pandas as pd
            from statistical_core import StatAnalyzer

            try:
                df = pd.read_csv(csv_path)
            except pd.errors.EmptyDataError:
                self.root.after(0, lambda: messagebox.showinfo("分析报告", "未采集到有效数据。"))
                self.root.after(0, lambda: self._set_run_state("done"))
                return

            settings = self._get_analysis_settings()
            cfg, path_df = self._load_audit_context(html_path)
            target_rel = str(cfg.get("reliability", "")).lower() if cfg else ""
            target_val = str(cfg.get("validity", "")).lower() if cfg else ""

            numeric_all = self._collect_scale_numeric(df)
            _, strict_items, _, coverage_map = self._select_scale_items(
                numeric_all,
                scope="strict_public",
                coverage_threshold=settings["coverage_threshold"],
                impute=False,
            )
            df_numeric, _, selected_items, _ = self._select_scale_items(
                numeric_all,
                scope=settings["scope"],
                coverage_threshold=settings["coverage_threshold"],
                impute=True,
            )

            sample_plan = int(cfg.get("count", len(df))) if cfg else len(df)
            sample_completed = len(df)
            sample_included = len(df_numeric) if not df_numeric.empty else 0

            item_numericizable = int(numeric_all.shape[1]) if numeric_all is not None else 0
            item_true_scale = self._estimate_scale_item_count_from_html(html_path)
            item_strict = len(strict_items)
            item_selected = len(selected_items)

            sample_n = sample_included
            item_n = df_numeric.shape[1]

            report = "=== 模拟数据质量分析报告 ===\n\n"
            report += f"样本量(纳入分析): {sample_n}\n"
            report += f"本次口径纳入题项数: {item_n}\n"
            report += f"问卷真正量表题总数(HTML识别): {item_true_scale}\n\n"
            report += self._build_parameter_summary(html_path)
            report += "【分析口径】\n"
            report += f"- 全样本口径: {self._analysis_scope_label(settings)}\n"
            report += f"- 分支门槛: n>={settings['branch_min_sample']} 且量表题>={settings['branch_min_items']}\n\n"

            report += "【样本与题项口径统计】\n"
            report += f"- 样本数量(计划/完成/纳入分析): {sample_plan} / {sample_completed} / {sample_included}\n"
            report += f"- 题项数量(识别到可数值化题项/真正量表题/按当前口径纳入): {item_numericizable} / {item_true_scale} / {item_selected}\n"
            report += f"- 严格公共题数量(100%覆盖): {item_strict}\n\n"

            report += "说明: 全样本测量分析依据“分析口径”纳入题项；分支题将按路径日志做分层分析。\n\n"
            report += "【全样本纳入题清单】\n"
            report += (", ".join(list(df_numeric.columns)) + "\n\n") if item_n > 0 else "无（请检查问卷量表题识别或口径门槛设置）。\n\n"
            if item_true_scale > 0 and item_n >= item_true_scale:
                report += f"提示: 当前全样本已覆盖全部 {item_true_scale} 题量表题。\n\n"
            else:
                report += f"提示: 当前全样本仅纳入 {item_n} 题（公共可比题），结论不代表整份 {item_true_scale} 题量表结构。\n\n"

            if sample_n < self.MIN_SAMPLE or item_n < self.MIN_SCALE_ITEMS:
                lack_sample = max(0, self.MIN_SAMPLE - sample_n)
                lack_items = max(0, self.MIN_SCALE_ITEMS - item_n)

                report += "【结果判定】\n"
                report += "样本/题项不足，暂不评价。\n"
                report += f"全样本门槛: 样本量>={self.MIN_SAMPLE}，本次口径纳入题项数>={self.MIN_SCALE_ITEMS}。\n"
                if lack_sample > 0:
                    report += f"- 还需补充样本: {lack_sample} 份。\n"
                if lack_items > 0:
                    report += f"- 还需补充量表题: {lack_items} 题。\n"
                report += "\n建议最小样本和最小题项：n>=30 且量表题>=3。\n"

                report += "\n【信度分析 (Cronbach's Alpha)】\n样本/题项不足，暂不评价\n"
                report += "\n【效度分析 (KMO)】\n样本/题项不足，暂不评价\n"
                report += "\n【区分度检验 (临界比值法)】\n样本/题项不足，暂不评价\n"
                branch_text, branch_meta = self._build_branch_analysis_sections(df, path_df, html_path, settings)
                report += branch_text
                report += self._build_auto_diagnostic_and_suggestions(
                    sample_n=sample_n,
                    item_n=item_n,
                    item_true_scale=item_true_scale,
                    item_selected=item_selected,
                    target_rel=target_rel,
                    target_val=target_val,
                    alpha=None,
                    kmo=None,
                    consistency=None,
                    settings=settings,
                    branch_meta=branch_meta,
                    cfa=None,
                    coverage_map=coverage_map,
                )

                analysis_meta = self._write_analysis_meta(
                    html_path,
                    {
                        "run_id": (cfg or {}).get("run_id", self.current_run_meta.get("run_id", "-")),
                        "seed": (cfg or {}).get("seed", self.current_run_meta.get("seed", "-")),
                        "analysis_settings": settings,
                        "sample_counts": {"planned": sample_plan, "completed": sample_completed, "included": sample_included},
                        "item_counts": {
                            "numericizable": item_numericizable,
                            "true_scale": item_true_scale,
                            "strict_public": item_strict,
                            "selected": item_selected,
                            "detected": item_numericizable,
                        },
                        "selected_items": list(df_numeric.columns),
                        "strict_public_items": strict_items,
                        "coverage_ratio": coverage_map,
                        "branch_sections": branch_meta,
                    },
                )
                report += f"分析快照文件: {os.path.join(os.path.dirname(html_path), 'analysis_meta.json')}\n"
                report += f"分析快照签名: {analysis_meta.get('analysis_signature', '-')}\n"
                report += self._build_audit_summary(html_path)

                self.root.after(0, lambda r=report: self._finalize_analysis_success(r, None))
                return

            alpha = StatAnalyzer.calculate_cronbach_alpha(df_numeric)
            kmo = StatAnalyzer.calculate_kmo(df_numeric)
            discrim = StatAnalyzer.calculate_discrimination(df_numeric)
            item_total_corr = StatAnalyzer.item_total_correlation(df_numeric)
            alpha_deleted = StatAnalyzer.alpha_if_deleted(df_numeric)
            efa = StatAnalyzer.run_efa_suite(df_numeric)
            theory_dims = self._infer_theory_dimensions(list(df_numeric.columns), html_path)
            cfa = StatAnalyzer.run_cfa_validation(
                df_numeric,
                n_factors=efa.get("n_factors_used", 1),
                dimension_groups=theory_dims if theory_dims else None,
            )

            kmo = float(efa.get("kmo", kmo))

            target_rel = str(cfg.get("reliability", "")).lower() if cfg else ""
            target_val = str(cfg.get("validity", "")).lower() if cfg else ""
            consistency = self._evaluate_target_consistency(alpha, kmo, target_rel, target_val)
            branch_text, branch_meta = self._build_branch_analysis_sections(df, path_df, html_path, settings)
            structural = self._evaluate_structural_risk(
                sample_n=sample_n,
                item_n=item_n,
                item_true_scale=item_true_scale,
                item_selected=item_selected,
                kmo=kmo,
                cfa=cfa,
                branch_meta=branch_meta,
                settings=settings,
            )
            consistency["structural_grade"] = structural["grade"]

            report += "【目标达成评级】\n"
            kmo_disp = "N/A" if not math.isfinite(kmo) else f"{kmo:.3f}"
            report += f"- 信度目标={target_rel or '-'}，当前Alpha={alpha:.3f}，等级={consistency['reliability']}\n"
            report += f"- 效度目标={target_val or '-'}，当前KMO={kmo_disp}，等级={consistency['validity']}\n"
            report += f"- 目标达成评级：{consistency['grade']}（A=达标，B=临界，C=偏离）\n\n"

            report += "【结构风险评级】\n"
            report += f"- 结构风险评级：{structural['grade']}（A=低风险，B=中风险，C=高风险）\n"
            report += f"- 结构风险评分：{structural['score']}\n"
            if structural["reasons"]:
                for reason in structural["reasons"][:5]:
                    report += f"- {reason}\n"
            else:
                report += "- 未识别到明显结构风险。\n"
            report += "\n"

            report += "【信度分析 (Cronbach's Alpha)】\n"
            report += f"Alpha系数: {alpha:.3f}\n"
            report += "判定标准: >=0.90极好, >=0.80良好, >=0.70可接受, <0.70建议优化。\n"

            report += "\n【效度分析 (KMO + Bartlett)】\n"
            report += f"相关矩阵方法: {efa.get('corr_method_used', 'pearson')}\n"
            report += f"KMO值: {kmo_disp}\n"
            report += f"Bartlett球形检验: chi2={efa['bartlett_chi2']:.2f}, p={self._format_p_value(efa['bartlett_p'])}\n"
            report += "判定标准: KMO>=0.70较好, Bartlett p<0.05 适合因子分析。\n"
            ratio = sample_n / max(item_n, 1)
            if not math.isfinite(kmo):
                report += "提示: KMO数值不稳定(N/A)，常见于样本偏少、题项高度共线或常量题项。\n"
            elif kmo <= 0.05:
                report += "提示: KMO接近0，常见于相关矩阵近奇异或样本-题项比过低。\n"
            if ratio < 5:
                report += f"提示: 当前样本-题项比={ratio:.2f}，建议>=5（更稳妥建议>=10）以提升EFA/KMO稳定性。\n"

            report += "\n【区分度检验 (临界比值法)】\n"
            sig_count = sum(1 for v in discrim.values() if v["significant"])
            report += f"显著差异题目数: {sig_count} / {len(discrim)}\n"
            report += "判定标准: 单题 p<0.05 视为区分度合格。\n"

            report += "\n【题级诊断】\n"
            report += "标准: CITC>=0.30较好；删除该题后Alpha若明显上升，说明题目可能拖累信度。\n"
            for col in df_numeric.columns:
                d = discrim.get(col, {"p": 1.0, "significant": False})
                report += (
                    f"- {col}: CITC={item_total_corr.get(col, 0.0):.3f}, "
                    f"Alpha_if_deleted={alpha_deleted.get(col, 0.0):.3f}, "
                    f"CR_p={self._format_p_value(d.get('p', 1.0))}, "
                    f"区分度={'合格' if d.get('significant', False) else '待优化'}\n"
                )

            report += "\n【EFA全套输出】\n"
            report += f"建议因子数(综合): {efa['suggested_factors']}\n"
            report += f"- Kaiser(特征根>1): {efa.get('suggested_factors_kaiser', efa['suggested_factors'])}\n"
            pa = efa.get("parallel_analysis", {})
            map_res = efa.get("map_test", {})
            report += f"- Parallel Analysis(主): {pa.get('suggested_factors', '-')}, (iter={pa.get('iterations', '-')}, pct={pa.get('percentile', '-')})\n"
            report += f"- MAP(辅): {map_res.get('suggested_factors', '-')}\n"
            report += f"- Scree拐点(辅): {efa.get('scree_elbow', '-')}\n"
            report += f"实际提取因子数: {efa['n_factors_used']}\n"
            eig_preview = ", ".join(f"{v:.3f}" for v in efa["eigenvalues"][:min(8, len(efa["eigenvalues"]))])
            report += f"特征根(前几项): {eig_preview}\n"
            for i, (vr, cr) in enumerate(zip(efa["variance_explained"], efa["variance_cumulative"]), 1):
                report += f"Factor{i}: 方差贡献率={vr:.3f}, 累计贡献率={cr:.3f}\n"

            report += "\n因子载荷(绝对值>=0.40通常可解释):\n"
            loading_df = efa["factor_loadings"]
            report += loading_df.round(3).to_string()

            report += "\n\n【补充验证 (Omega + CFA)】\n"
            omega = efa.get("omega_total")
            omega_disp = "N/A" if not isinstance(omega, (int, float)) or not math.isfinite(float(omega)) else f"{float(omega):.3f}"
            report += f"Omega_total: {omega_disp} (通常>=0.70较可接受)\n"
            if theory_dims:
                report += f"CFA理论维度数: {len(theory_dims)}（每维>=3题）\n"
            else:
                report += "CFA理论维度数: 0（已回退到探索分组或跳过）\n"
            if cfa.get("available"):
                report += (
                    f"CFA拟合: CFI={cfa.get('cfi', float('nan')):.3f}, "
                    f"TLI={cfa.get('tli', float('nan')):.3f}, "
                    f"RMSEA={cfa.get('rmsea', float('nan')):.3f}, "
                    f"SRMR={cfa.get('srmr', float('nan')):.3f}\n"
                )
                report += "参考阈值: CFI/TLI>=0.90, RMSEA<=0.08, SRMR<=0.08。\n"
            else:
                report += f"CFA拟合: 未执行 ({cfa.get('reason', '无')})\n"

            branch_text, branch_meta = self._build_branch_analysis_sections(df, path_df, html_path, settings)
            report += branch_text
            report += self._build_auto_diagnostic_and_suggestions(
                sample_n=sample_n,
                item_n=item_n,
                item_true_scale=item_true_scale,
                item_selected=item_selected,
                target_rel=target_rel,
                target_val=target_val,
                alpha=alpha,
                kmo=kmo,
                consistency=consistency,
                settings=settings,
                branch_meta=branch_meta,
                cfa=cfa,
                coverage_map=coverage_map,
            )

            analysis_meta = self._write_analysis_meta(
                html_path,
                {
                    "run_id": (cfg or {}).get("run_id", self.current_run_meta.get("run_id", "-")),
                    "seed": (cfg or {}).get("seed", self.current_run_meta.get("seed", "-")),
                    "analysis_settings": settings,
                    "sample_counts": {"planned": sample_plan, "completed": sample_completed, "included": sample_included},
                    "item_counts": {
                        "numericizable": item_numericizable,
                        "true_scale": item_true_scale,
                        "strict_public": item_strict,
                        "selected": item_selected,
                        "detected": item_numericizable,
                    },
                    "selected_items": list(df_numeric.columns),
                    "strict_public_items": strict_items,
                    "coverage_ratio": coverage_map,
                    "branch_sections": branch_meta,
                    "consistency": consistency,
                    "target_consistency": consistency,
                    "structural_risk": structural,
                },
            )
            report += f"\n分析快照文件: {os.path.join(os.path.dirname(html_path), 'analysis_meta.json')}\n"
            report += f"分析快照签名: {analysis_meta.get('analysis_signature', '-')}\n"
            report += self._build_audit_summary(html_path)

            self.root.after(0, lambda r=report, c=consistency: self._finalize_analysis_success(r, c))
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self._finalize_analysis_error(msg))

    def _collect_auto_diagnostic_issues(
        self,
        *,
        sample_n,
        item_n,
        item_true_scale,
        item_selected,
        target_rel,
        target_val,
        alpha,
        kmo,
        settings,
        branch_meta,
        cfa,
        coverage_map,
    ):
        issues = []

        if sample_n < 50:
            issues.append(("高", "sample", f"样本量偏小(n={sample_n})，统计量波动更大。"))
        elif sample_n < 100:
            issues.append(("中", "sample", f"样本量仍偏少(n={sample_n})，建议继续增样本提升稳定性。"))

        if item_n < 6:
            issues.append(("高", "item_count", f"本次口径仅纳入 {item_n} 题，题项偏少会显著限制KMO/CFA稳定性。"))
        elif item_n < 10:
            issues.append(("中", "item_count", f"本次口径纳入题项仅 {item_n} 题，维度识别能力仍偏弱。"))

        if item_true_scale > 0 and item_selected < item_true_scale:
            gap_ratio = item_selected / max(item_true_scale, 1)
            level = "高" if gap_ratio < 0.5 else "中"
            issues.append((
                level,
                "coverage_loss",
                f"问卷真量表题共 {item_true_scale} 题，但当前口径仅纳入 {item_selected} 题；跳题导致可比题减少。",
            ))

        if isinstance(alpha, (int, float)) and math.isfinite(alpha):
            if target_rel == "high" and alpha < 0.70:
                issues.append(("高", "alpha", f"信度明显未达目标：Alpha={alpha:.3f}（high目标通常>=0.80）。"))
            elif target_rel == "high" and alpha < 0.80:
                issues.append(("中", "alpha", f"信度接近但未达目标：Alpha={alpha:.3f}（high目标通常>=0.80）。"))
            elif target_rel == "medium" and alpha < 0.70:
                issues.append(("中", "alpha", f"信度未达目标：Alpha={alpha:.3f}（medium目标通常>=0.70）。"))

        if isinstance(kmo, (int, float)) and math.isfinite(kmo):
            if target_val == "high" and kmo < 0.50:
                issues.append(("高", "kmo", f"效度明显未达目标：KMO={kmo:.3f}（high目标通常>=0.70）。"))
            elif target_val == "high" and kmo < 0.70:
                issues.append(("中", "kmo", f"效度未达目标：KMO={kmo:.3f}（high目标通常>=0.70）。"))
            elif target_val == "medium" and kmo < 0.60:
                issues.append(("中", "kmo", f"效度未达目标：KMO={kmo:.3f}（medium目标通常>=0.60）。"))

        if cfa and cfa.get("available"):
            cfi = cfa.get("cfi", float("nan"))
            rmsea = cfa.get("rmsea", float("nan"))
            cfi_bad = isinstance(cfi, (int, float)) and math.isfinite(float(cfi)) and cfi < 0.90
            rmsea_bad = isinstance(rmsea, (int, float)) and math.isfinite(float(rmsea)) and rmsea > 0.08
            if cfi_bad or rmsea_bad:
                if (isinstance(cfi, (int, float)) and math.isfinite(float(cfi)) and cfi < 0.80) or (
                    isinstance(rmsea, (int, float)) and math.isfinite(float(rmsea)) and rmsea > 0.12
                ):
                    issues.append(("高", "cfa", f"CFA拟合偏差较大(CFI={cfi:.3f}, RMSEA={rmsea:.3f})。"))
                else:
                    issues.append(("中", "cfa", f"CFA拟合未达建议阈值(CFI={cfi:.3f}, RMSEA={rmsea:.3f})。"))
        elif item_n >= 3:
            issues.append(("低", "cfa", "CFA未执行或不可用，建议确保每个理论维度至少3题且同群体可回答。"))

        if coverage_map and settings and settings.get("scope") == "coverage":
            threshold = float(settings.get("coverage_threshold", self.DEFAULT_COVERAGE_THRESHOLD))
            low_cov = sum(1 for _, ratio in coverage_map.items() if float(ratio) < threshold)
            if low_cov >= 8:
                issues.append(("中", "coverage", f"有 {low_cov} 题覆盖率低于阈值({threshold:.2f})，全样本可比性受限。"))
            elif low_cov >= 3:
                issues.append(("低", "coverage", f"有 {low_cov} 题覆盖率低于阈值({threshold:.2f})，建议做分支分层复核。"))

        if branch_meta and len(branch_meta) >= 2:
            stable_branches = [b for b in branch_meta if not b.get("excluded_from_overall", False)]
            exploratory_count = sum(1 for b in branch_meta if b.get("exploratory_only", False))
            if len(stable_branches) >= 2:
                item_counts = [int(x.get("item_count", 0)) for x in stable_branches]
                if max(item_counts) - min(item_counts) >= 10:
                    issues.append(("高", "branch_gap", "分支间题项覆盖差异很大，混合建模会明显拉低全样本效度。"))
                elif max(item_counts) - min(item_counts) >= 6:
                    issues.append(("中", "branch_gap", "分支间题项覆盖差异较大，混合建模会拉低全样本效度。"))
            if exploratory_count > 0:
                issues.append(("中", "branch_np", f"有 {exploratory_count} 个分支 n/p<5，仅可作探索性参考。"))

        return issues

    def _build_issue_based_suggestions(self, issues, settings):
        tags = {tag for _, tag, _ in issues}
        suggestions = []

        if "sample" in tags:
            suggestions.append("优先扩充样本量：至少>=100（更稳妥>=200）。")
        if "item_count" in tags or "coverage_loss" in tags:
            suggestions.append("增加全样本可共同回答的核心量表题，建议公共题>=8且每维>=3题。")
        if "branch_gap" in tags or "coverage" in tags:
            suggestions.append("分支题按路径分层独立评估，避免把互斥分支题直接混在同一全样本模型。")
        if "alpha" in tags:
            suggestions.append("针对低CITC题目优先改写题干，减少双重表述并统一语义方向。")
        if "kmo" in tags:
            suggestions.append("按理论维度补题，并保证同维题项语义一致，提升结构效度。")
        if "cfa" in tags:
            suggestions.append("按理论维度重建模型，控制交叉载荷；必要时拆分多义题或调整分支结构。")

        if settings and settings.get("scope") == "strict_public":
            suggestions.append("当前为严格公共题口径；如题项过少，可切换覆盖率口径(0.60~0.70)做对照分析。")

        if not suggestions:
            suggestions.append("当前整体达标，可继续扩大样本并复跑验证稳定性。")

        return [f"{i}) {text}" for i, text in enumerate(suggestions, 1)]

    def _build_auto_diagnostic_and_suggestions(
        self,
        *,
        sample_n,
        item_n,
        item_true_scale,
        item_selected,
        target_rel,
        target_val,
        alpha,
        kmo,
        consistency,
        settings,
        branch_meta,
        cfa,
        coverage_map,
    ):
        lines = ["\n【为何未达标的自动诊断解释】", "说明: 每条原因按影响分级为 高/中/低。"]
        severity_rank = {"高": 0, "中": 1, "低": 2}

        issues = self._collect_auto_diagnostic_issues(
            sample_n=sample_n,
            item_n=item_n,
            item_true_scale=item_true_scale,
            item_selected=item_selected,
            target_rel=target_rel,
            target_val=target_val,
            alpha=alpha,
            kmo=kmo,
            settings=settings,
            branch_meta=branch_meta,
            cfa=cfa,
            coverage_map=coverage_map,
        )

        if not issues:
            lines.append("- [低] 未发现明显结构性短板；当前结果基本与目标一致。")
        else:
            issues.sort(key=lambda x: severity_rank.get(x[0], 9))
            for i, (level, _, reason) in enumerate(issues, 1):
                lines.append(f"{i}) [{level}] {reason}")

        lines.append("\n【问卷优化建议】")
        lines.extend(self._build_issue_based_suggestions(issues, settings))
        return "\n".join(lines) + "\n"

    def _build_branch_analysis_sections(self, df, path_df, html_path, settings):
        from statistical_core import StatAnalyzer

        txt = "\n【分支分层分析 (自动)】\n"
        txt += "规则: 依据路径日志visited_questions自动分层；每层按当前分析口径纳入题项。\n"
        txt += "警戒: 当分支 n/p<5 时仅作探索性参考；n/p<3 为高风险探索，不纳入总体结论。\n"
        branch_item_lines = []
        branch_meta = []

        if path_df is None or path_df.empty or "sample_id" not in path_df.columns:
            txt += "未找到可用路径日志，跳过分层分析。\n"
        else:
            id_col = "_sample_id" if "_sample_id" in df.columns else None
            top_branches = path_df.groupby("visited_questions").size().sort_values(ascending=False).head(6)
            shown = 0

            for branch_trace, b_n in top_branches.items():
                if b_n < settings["branch_min_sample"]:
                    continue
                branch_ids = set(path_df[path_df["visited_questions"] == branch_trace]["sample_id"].astype(int).tolist())
                if id_col:
                    sub_df = df[df[id_col].astype(int).isin(branch_ids)]
                else:
                    sub_df = df.iloc[[i - 1 for i in sorted(branch_ids) if 1 <= i <= len(df)]]

                sub_all_numeric = self._collect_scale_numeric(sub_df)
                sub_numeric, sub_strict_items, sub_selected_items, _ = self._select_scale_items(
                    sub_all_numeric,
                    scope=settings["scope"],
                    coverage_threshold=settings["coverage_threshold"],
                    impute=True,
                )
                if len(sub_numeric) < settings["branch_min_sample"] or sub_numeric.shape[1] < settings["branch_min_items"]:
                    continue

                n_per_item = len(sub_numeric) / max(sub_numeric.shape[1], 1)
                exploratory_only = n_per_item < 5
                high_risk_np = n_per_item < 3

                b_alpha = StatAnalyzer.calculate_cronbach_alpha(sub_numeric)
                b_efa = StatAnalyzer.run_efa_suite(sub_numeric)
                b_kmo = b_efa.get("kmo", float("nan"))
                b_dims = self._infer_theory_dimensions(list(sub_numeric.columns), html_path)
                b_cfa = StatAnalyzer.run_cfa_validation(
                    sub_numeric,
                    n_factors=b_efa.get("n_factors_used", 1),
                    dimension_groups=b_dims if b_dims else None,
                )

                shown += 1
                trace_disp = str(branch_trace)
                if len(trace_disp) > 120:
                    trace_disp = trace_disp[:117] + "..."
                branch_item_lines.append(
                    f"- 分支#{shown} (n={len(sub_numeric)}, strict={len(sub_strict_items)}, selected={len(sub_selected_items)}, trace={trace_disp}): " + ", ".join(list(sub_numeric.columns))
                )

                tag = ""
                if exploratory_only:
                    tag = " [探索性参考: n/p<3, 高风险]" if high_risk_np else " [探索性参考: n/p<5]"

                txt += (
                    f"- 分支#{shown}{tag}: n={len(sub_numeric)}, 题项={sub_numeric.shape[1]}, n/p={n_per_item:.2f}, "
                    f"Alpha={b_alpha:.3f}, "
                    f"KMO={(f'{b_kmo:.3f}' if isinstance(b_kmo, (int, float)) and math.isfinite(float(b_kmo)) else 'N/A')}, "
                    f"PA={b_efa.get('parallel_analysis', {}).get('suggested_factors', '-')}, "
                    f"MAP={b_efa.get('map_test', {}).get('suggested_factors', '-')}, "
                    f"Scree={b_efa.get('scree_elbow', '-')}"
                )
                if b_cfa.get("available"):
                    txt += f", CFA(CFI={b_cfa.get('cfi', float('nan')):.3f}, RMSEA={b_cfa.get('rmsea', float('nan')):.3f})"
                if exploratory_only:
                    txt += "，不纳入总体结论"
                txt += "\n"

                branch_meta.append(
                    {
                        "branch_index": shown,
                        "trace": str(branch_trace),
                        "sample_count": int(len(sub_numeric)),
                        "item_count": int(sub_numeric.shape[1]),
                        "strict_item_count": int(len(sub_strict_items)),
                        "selected_item_count": int(len(sub_selected_items)),
                        "selected_items": list(sub_numeric.columns),
                        "alpha": float(b_alpha) if isinstance(b_alpha, (int, float)) and math.isfinite(float(b_alpha)) else None,
                        "kmo": float(b_kmo) if isinstance(b_kmo, (int, float)) and math.isfinite(float(b_kmo)) else None,
                        "cfa_available": bool(b_cfa.get("available")),
                        "cfa_cfi": float(b_cfa.get("cfi")) if b_cfa.get("available") and isinstance(b_cfa.get("cfi"), (int, float)) and math.isfinite(float(b_cfa.get("cfi"))) else None,
                        "cfa_rmsea": float(b_cfa.get("rmsea")) if b_cfa.get("available") and isinstance(b_cfa.get("rmsea"), (int, float)) and math.isfinite(float(b_cfa.get("rmsea"))) else None,
                        "n_per_item": float(n_per_item),
                        "exploratory_only": bool(exploratory_only),
                        "excluded_from_overall": bool(exploratory_only),
                    }
                )

            if shown == 0:
                txt += f"无满足门槛的分层（n>={settings['branch_min_sample']} 且量表题>={settings['branch_min_items']}）。\n"

        txt += "\n【每个分支纳入题清单】\n"
        txt += "\n".join(branch_item_lines) + "\n" if branch_item_lines else "无可展示分支题清单（未形成可分析分层）。\n"
        return txt, branch_meta

    def _finalize_analysis_success(self, report_text, consistency):
        if consistency is None:
            self._update_consistency_banner(None)
        else:
            self._update_consistency_banner(consistency)
        AnalysisWindow(self.root, report_text)
        self.status_var.set("任务完成")
        self._set_run_state("done")

    def _finalize_analysis_error(self, error_message):
        self._set_run_state("error")
        messagebox.showerror("分析错误", f"计算指标时出错: {error_message}")

    def _format_p_value(self, p):
        try:
            p = float(p)
        except Exception:
            return "N/A"
        if not math.isfinite(p):
            return "N/A"
        if p <= 0:
            return "<1e-16"
        if p < 1e-4:
            return f"{p:.2e}"
        return f"{p:.4f}"

    def _estimate_scale_item_count_from_html(self, html_path):
        if not html_path or not os.path.exists(html_path):
            return 0
        try:
            with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
        except Exception:
            return 0

        # True scale items: explicit scale radio items + matrix scale rows.
        scale_radio_count = len(re.findall(r'data-type="scale_radio"', html))
        matrix_row_names = set(re.findall(r'name="q\d+_row\d+"', html))
        return int(scale_radio_count + len(matrix_row_names))

    def _refresh_latent_dim_options(self, html_path):
        item_n = self._estimate_scale_item_count_from_html(html_path)
        if item_n <= 0:
            max_dim = self.MAX_LATENT_DIMS
        elif item_n < 3:
            max_dim = 1
        else:
            max_dim = max(1, min(self.MAX_LATENT_DIMS, item_n // 3))

        values = tuple(range(1, max_dim + 1))
        self.dims_combo["values"] = values

        try:
            current = int(self.latent_dims_var.get())
        except Exception:
            current = 1
        if current not in values:
            self.latent_dims_var.set(values[-1])


class AnalysisWindow(ttk.Toplevel):
    def __init__(self, parent, report_text):
        super().__init__(master=parent)
        self.title("数据质量分析报告")
        self.geometry("500x600")
        self.report_text = report_text

        txt = ttk.Text(self, font=("Consolas", 10), padx=10, pady=10)
        txt.pack(fill=BOTH, expand=YES)
        txt.insert("1.0", report_text)
        self._apply_level_tags(txt)
        txt.configure(state="disabled")

        btn_row = ttk.Frame(self)
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text="保存分析结果", command=self._save_report, bootstyle="primary").pack(side=LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="关闭", command=self.destroy, bootstyle="secondary").pack(side=LEFT)

    def _save_report(self):
        path = filedialog.asksaveasfilename(
            title="保存分析结果",
            defaultextension=".txt",
            initialfile="analysis_report.txt",
            filetypes=[("Text Files", "*.txt"), ("Markdown", "*.md"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.report_text)
            messagebox.showinfo("保存成功", f"分析结果已保存:\n{path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _apply_level_tags(self, text_widget):
        text_widget.tag_configure("ok", foreground="#1f9d55")
        text_widget.tag_configure("warn", foreground="#d39e00")
        text_widget.tag_configure("bad", foreground="#d9534f")
        text_widget.tag_configure("grade_a", foreground="#1f9d55", font=("Consolas", 10, "bold"))
        text_widget.tag_configure("grade_b", foreground="#d39e00", font=("Consolas", 10, "bold"))
        text_widget.tag_configure("grade_c", foreground="#d9534f", font=("Consolas", 10, "bold"))

        for keyword, tag in (
            ("等级=达标", "ok"),
            ("等级=临界", "warn"),
            ("等级=偏离", "bad"),
            ("总体评级：A", "grade_a"),
            ("总体评级：B", "grade_b"),
            ("总体评级：C", "grade_c"),
            ("目标达成评级：A", "grade_a"),
            ("目标达成评级：B", "grade_b"),
            ("目标达成评级：C", "grade_c"),
            ("结构风险评级：A", "grade_a"),
            ("结构风险评级：B", "grade_b"),
            ("结构风险评级：C", "grade_c"),
        ):
            start = "1.0"
            while True:
                pos = text_widget.search(keyword, start, stopindex="end")
                if not pos:
                    break
                end = f"{pos}+{len(keyword)}c"
                text_widget.tag_add(tag, pos, end)
                start = end


if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    app = SurveyApp(app_root)
    app_root.mainloop()
