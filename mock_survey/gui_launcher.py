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

    def __init__(self, root):
        self.root = root
        self.root.title("自动化问卷模拟系统 v1.0")
        self.root.geometry("1200x950")

        self.style = ttk.Style(theme="cosmo")
        self.phase_var = ttk.StringVar(value="待机")
        self.status_var = ttk.StringVar(value="准备就绪")
        self.overall_grade_var = ttk.StringVar(value="总体评级: -")
        self.rel_target_var = ttk.StringVar(value="信度目标一致性: -")
        self.val_target_var = ttk.StringVar(value="效度目标一致性: -")

        self.stop_event = threading.Event()
        self.is_running = False
        self.current_run_meta = {}

        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill=BOTH, expand=YES)

        header = ttk.Frame(main_frame)
        header.pack(fill=X, pady=(0, 20))
        ttk.Label(header, text="问卷模拟大师", font=("Helvetica", 24, "bold"), bootstyle="primary").pack(side=LEFT)
        ttk.Label(header, text="v1.0", font=("Helvetica", 12), bootstyle="secondary").pack(side=LEFT, padx=10, pady=(10, 0))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=YES, fill=BOTH)

        self.tab_gen = ttk.Frame(self.notebook, padding=20)
        self.tab_sim = ttk.Frame(self.notebook, padding=20)
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

        left_panel = ttk.Frame(root_row)
        left_panel.pack(side=LEFT, fill=BOTH, expand=YES)

        right_panel = ttk.Labelframe(root_row, text="运行日志")
        right_panel.pack(side=RIGHT, fill=BOTH, padx=(12, 0), ipadx=8, ipady=8)

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
        d_combo = ttk.Combobox(row2, textvariable=self.latent_dims_var, state="readonly", width=8)
        d_combo["values"] = (1, 2, 3, 4)
        d_combo.pack(side=LEFT, padx=5)

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
        d_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_measurement_help())
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
        action_frame.pack(fill=X, pady=(16, 10), ipadx=6, ipady=6)

        self.btn_start = tk.Button(
            action_frame,
            text="开始模拟 Start",
            command=self.start_simulation,
            width=18,
            font=("Microsoft YaHei", 11, "bold"),
            bg="#28a745",
            fg="white",
            activebackground="#218838",
            activeforeground="white",
            relief="raised",
            bd=2,
            padx=10,
            pady=8,
        )
        self.btn_start.pack(side=LEFT, padx=(0, 12), pady=4)

        self.btn_stop = tk.Button(
            action_frame,
            text="停止 Stop",
            command=self.stop_simulation,
            width=14,
            font=("Microsoft YaHei", 11, "bold"),
            state="disabled",
            bg="#dc3545",
            fg="white",
            activebackground="#c82333",
            activeforeground="white",
            relief="raised",
            bd=2,
            padx=10,
            pady=8,
        )
        self.btn_stop.pack(side=LEFT, pady=4)

        phase_wrap = ttk.Frame(left_panel)
        phase_wrap.pack(fill=X, pady=(6, 4))
        ttk.Label(phase_wrap, text="当前阶段:", bootstyle="secondary").pack(side=LEFT)
        ttk.Label(phase_wrap, textvariable=self.phase_var, bootstyle="info").pack(side=LEFT, padx=8)
        ttk.Label(phase_wrap, text="状态:", bootstyle="secondary").pack(side=LEFT, padx=(16, 0))
        ttk.Label(phase_wrap, textvariable=self.status_var, bootstyle="secondary").pack(side=LEFT, padx=6)

        self.progress_var = ttk.DoubleVar()
        self.progress_bar = ttk.Progressbar(left_panel, variable=self.progress_var, maximum=100, bootstyle="striped-success", mode="determinate")
        self.progress_bar.pack(fill=X, pady=(2, 10))

        self.log_text = ttk.Text(right_panel, width=50, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill=BOTH, expand=YES, side=LEFT)
        scroll = ttk.Scrollbar(right_panel, orient=VERTICAL, command=self.log_text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)


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
        f = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if f:
            self.txt_path_var.set(f)

    def browse_html_out(self):
        f = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Files", "*.html")])
        if f:
            self.html_out_var.set(f)

    def browse_html_in(self):
        f = filedialog.askopenfilename(filetypes=[("HTML Files", "*.html")])
        if f:
            self.sim_html_var.set(f)

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
            os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
            survey_generator.generate_html(data, html_path)
            self.status_var.set(f"成功生成: {os.path.basename(html_path)}")
            self.sim_html_var.set(html_path)
            messagebox.showinfo("成功", "问卷网页生成完毕！\n已自动填入模拟页面，请切换到 '智能模拟' 标签页开始运行。")
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

    def _update_consistency_banner(self, result=None):
        if not result:
            self.overall_grade_var.set("总体评级: -")
            self.rel_target_var.set("信度目标一致性: -")
            self.val_target_var.set("效度目标一致性: -")
            self.grade_label.configure(bootstyle="secondary")
            self.rel_level_label.configure(bootstyle="secondary")
            self.val_level_label.configure(bootstyle="secondary")
            return

        grade = result.get("grade", "-")
        rel = result.get("reliability", "-")
        val = result.get("validity", "-")

        grade_style = {"A": "success", "B": "warning", "C": "danger"}.get(grade, "secondary")
        self.overall_grade_var.set(f"总体评级: {grade}")
        self.rel_target_var.set(f"信度目标一致性: {rel}")
        self.val_target_var.set(f"效度目标一致性: {val}")

        self.grade_label.configure(bootstyle=grade_style)
        self.rel_level_label.configure(bootstyle=self._consistency_bootstyle(rel))
        self.val_level_label.configure(bootstyle=self._consistency_bootstyle(val))

    def replay_from_config(self):
        html_path = self.sim_html_var.get()
        if not html_path:
            messagebox.showwarning("提示", "请先选择目标 HTML。")
            return

        cfg, _ = self._load_audit_context(html_path)
        if not cfg:
            messagebox.showinfo("复现入口", "未找到 config.json。请先运行一次模拟，或检查目标 HTML 同目录。")
            return

        try:
            count = int(cfg.get("count", self.MIN_SAMPLE))
            self.sim_count_var.set(max(self.MIN_SAMPLE, count))
            self.bias_var.set(str(cfg.get("bias", self.bias_var.get())))
            self.reliability_var.set(str(cfg.get("reliability", self.reliability_var.get())))
            self.validity_var.set(str(cfg.get("validity", self.validity_var.get())))
            self.latent_dims_var.set(int(cfg.get("latent_dims", self.latent_dims_var.get())))
            self.headless_var.set(bool(cfg.get("headless", self.headless_var.get())))
            self._update_measurement_help()
            self._update_bias_help()
            self.log(f"已从 config.json 回填参数: run_id={cfg.get('run_id', '-')}, seed={cfg.get('seed', '-')}")
            messagebox.showinfo(
                "复现入口",
                "已回填上次运行参数。\n复现方式: 保持参数不变后再次点击“开始模拟”。\n可复现关键字段见报告中的“审计摘要”。",
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
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.phase_var.set("正在填写问卷...")
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.stop()
        elif state == "stopping":
            self.btn_stop.configure(state="disabled")
            self.phase_var.set("正在停止...")
        elif state == "analyzing":
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self.phase_var.set("正在分析问卷结果...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(12)
        elif state == "done":
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.phase_var.set("完成")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
        elif state == "error":
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.phase_var.set("异常")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")

    def _extract_scale_dataframe(self, df_raw):
        import pandas as pd

        # Only questionnaire columns participate in psychometrics; exclude audit/meta fields.
        question_cols = [c for c in df_raw.columns if str(c).startswith("Q")]
        if not question_cols:
            return pd.DataFrame()

        expanded_parts = []
        for col in question_cols:
            s = df_raw[col]
            non_null = s.dropna().astype(str)
            if non_null.empty:
                continue

            if non_null.str.contains(r"\|", regex=True).mean() >= 0.2:
                split_df = s.astype(str).str.split("|", expand=True, regex=False)
                split_df.columns = [f"{col}_r{i+1}" for i in range(split_df.shape[1])]
                expanded_parts.append(split_df)
            else:
                expanded_parts.append(pd.DataFrame({col: s}))

        if not expanded_parts:
            return pd.DataFrame()

        work = pd.concat(expanded_parts, axis=1)
        work = work.replace({"": None, "None": None, "nan": None})
        numeric = work.apply(pd.to_numeric, errors="coerce")

        # Skip logic can legitimately reduce answered ratio; keep columns answered by >=30% samples.
        valid_cols = numeric.columns[numeric.notna().mean() >= 0.3]
        numeric = numeric[valid_cols]
        if numeric.empty:
            return numeric

        # Median imputation keeps sample size stable for EFA while preserving ordinal center.
        for col in numeric.columns:
            med = numeric[col].median()
            numeric[col] = numeric[col].fillna(med if pd.notna(med) else numeric[col].mode().iloc[0] if not numeric[col].mode().empty else 3)

        return numeric

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
            lines.append("未找到 config.json（无法显示运行签名与关键参数）。")

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
        try:
            csv_path = os.path.join(os.path.dirname(html_path), "survey_data_collected.csv")
            if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
                messagebox.showinfo("分析报告", "未采集到有效数据，请检查模拟过程。")
                self._set_run_state("done")
                return

            import pandas as pd
            from statistical_core import StatAnalyzer

            try:
                df = pd.read_csv(csv_path)
            except pd.errors.EmptyDataError:
                messagebox.showinfo("分析报告", "未采集到有效数据。")
                self._set_run_state("done")
                return

            df_numeric = self._extract_scale_dataframe(df)
            sample_n = len(df_numeric)
            item_n = df_numeric.shape[1]

            report = "=== 模拟数据质量分析报告 ===\n\n"
            report += f"样本量: {sample_n}\n"
            report += f"量表题数: {item_n}\n\n"
            report += self._build_parameter_summary(html_path)

            if sample_n < self.MIN_SAMPLE or item_n < self.MIN_SCALE_ITEMS:
                lack_sample = max(0, self.MIN_SAMPLE - sample_n)
                lack_items = max(0, self.MIN_SCALE_ITEMS - item_n)

                report += "【结果判定】\n"
                report += "样本/题项不足，暂不评价。\n"
                report += f"当前门槛: 样本量>={self.MIN_SAMPLE}，量表题数>={self.MIN_SCALE_ITEMS}。\n"
                if lack_sample > 0:
                    report += f"- 还需补充样本: {lack_sample} 份。\n"
                if lack_items > 0:
                    report += f"- 还需补充量表题: {lack_items} 题。\n"
                report += "\n建议最小样本和最小题项：n>=30 且量表题>=3。\n"

                report += "\n【信度分析 (Cronbach's Alpha)】\n样本/题项不足，暂不评价\n"
                report += "\n【效度分析 (KMO)】\n样本/题项不足，暂不评价\n"
                report += "\n【区分度检验 (临界比值法)】\n样本/题项不足，暂不评价\n"
                report += self._build_audit_summary(html_path)
                self._update_consistency_banner(None)
                AnalysisWindow(self.root, report)
                self.status_var.set("任务完成")
                self._set_run_state("done")
                return

            alpha = StatAnalyzer.calculate_cronbach_alpha(df_numeric)
            kmo = StatAnalyzer.calculate_kmo(df_numeric)
            discrim = StatAnalyzer.calculate_discrimination(df_numeric)
            item_total = StatAnalyzer.item_total_correlation(df_numeric)
            alpha_deleted = StatAnalyzer.alpha_if_deleted(df_numeric)
            efa = StatAnalyzer.run_efa_suite(df_numeric)

            # Keep one KMO source in report and target-consistency check.
            kmo = float(efa.get("kmo", kmo))

            cfg, _ = self._load_audit_context(html_path)
            target_rel = str(cfg.get("reliability", "")).lower() if cfg else ""
            target_val = str(cfg.get("validity", "")).lower() if cfg else ""
            consistency = self._evaluate_target_consistency(alpha, kmo, target_rel, target_val)
            self._update_consistency_banner(consistency)

            report += "【目标一致性检查】\n"
            kmo_disp = "N/A" if not math.isfinite(kmo) else f"{kmo:.3f}"
            report += f"- 信度目标={target_rel or '-'}，当前Alpha={alpha:.3f}，等级={consistency['reliability']}\n"
            report += f"- 效度目标={target_val or '-'}，当前KMO={kmo_disp}，等级={consistency['validity']}\n"
            report += f"- 总体评级：{consistency['grade']}（A=达标，B=临界，C=偏离）\n\n"

            report += "【信度分析 (Cronbach's Alpha)】\n"
            report += f"Alpha系数: {alpha:.3f}\n"
            report += "判定标准: >=0.90极好, >=0.80良好, >=0.70可接受, <0.70建议优化。\n"

            report += "\n【效度分析 (KMO + Bartlett)】\n"
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
                    f"- {col}: CITC={item_total.get(col, 0.0):.3f}, "
                    f"Alpha_if_deleted={alpha_deleted.get(col, 0.0):.3f}, "
                    f"CR_p={self._format_p_value(d.get('p', 1.0))}, "
                    f"区分度={'合格' if d.get('significant', False) else '待优化'}\n"
                )

            report += "\n【EFA全套输出】\n"
            report += f"建议因子数(特征根>1): {efa['suggested_factors']}\n"
            report += f"实际提取因子数: {efa['n_factors_used']}\n"
            eig_preview = ", ".join(f"{v:.3f}" for v in efa["eigenvalues"][:min(8, len(efa["eigenvalues"]))])
            report += f"特征根(前几项): {eig_preview}\n"
            for i, (vr, cr) in enumerate(zip(efa["variance_explained"], efa["variance_cumulative"]), 1):
                report += f"Factor{i}: 方差贡献率={vr:.3f}, 累计贡献率={cr:.3f}\n"

            report += "\n因子载荷(绝对值>=0.40通常可解释):\n"
            loading_df = efa["factor_loadings"]
            report += loading_df.round(3).to_string()
            report += "\n\n【优化建议】\n"
            report += "1) 若KMO<0.70: 增加同维度题项并统一量表语义。\n"
            report += "2) 若单题CITC<0.30: 优先改写该题或移除。\n"
            report += "3) 若CR不显著: 调整题干使高低分群体更易区分。\n"
            report += "4) 若因子交叉载荷高: 减少双重表述，按单维度拆题。\n"
            report += self._build_audit_summary(html_path)

            AnalysisWindow(self.root, report)
            self.status_var.set("任务完成")
            self._set_run_state("done")
        except Exception as e:
            self._set_run_state("error")
            messagebox.showerror("分析错误", f"计算指标时出错: {e}")

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


class AnalysisWindow(ttk.Toplevel):
    def __init__(self, parent, report_text):
        super().__init__(master=parent)
        self.title("数据质量分析报告")
        self.geometry("500x600")

        txt = ttk.Text(self, font=("Consolas", 10), padx=10, pady=10)
        txt.pack(fill=BOTH, expand=YES)
        txt.insert("1.0", report_text)
        self._apply_level_tags(txt)
        txt.configure(state="disabled")

        ttk.Button(self, text="关闭", command=self.destroy, bootstyle="secondary").pack(pady=10)

    def _apply_level_tags(self, text_widget):
        text_widget.tag_configure("ok", foreground="#1f9d55")
        text_widget.tag_configure("warn", foreground="#d39e00")
        text_widget.tag_configure("bad", foreground="#d9534f")
        text_widget.tag_configure("grade_a", foreground="#1f9d55", font=("Consolas", 10, "bold"))
        text_widget.tag_configure("grade_b", foreground="#d39e00", font=("Consolas", 10, "bold"))
        text_widget.tag_configure("grade_c", foreground="#d9534f", font=("Consolas", 10, "bold"))

        for keyword, tag in (("等级=达标", "ok"), ("等级=临界", "warn"), ("等级=偏离", "bad"), ("总体评级：A", "grade_a"), ("总体评级：B", "grade_b"), ("总体评级：C", "grade_c")):
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
