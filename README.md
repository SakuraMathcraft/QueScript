# QueScript

<div align="center">

本地优先、可审计的问卷模拟与测量分析工具。

[![Stars](https://img.shields.io/github/stars/SakuraMathcraft/QueScript?style=for-the-badge)](https://github.com/SakuraMathcraft/QueScript/stargazers)
[![Forks](https://img.shields.io/github/forks/SakuraMathcraft/QueScript?style=for-the-badge)](https://github.com/SakuraMathcraft/QueScript/network/members)
[![Issues](https://img.shields.io/github/issues/SakuraMathcraft/QueScript?style=for-the-badge)](https://github.com/SakuraMathcraft/QueScript/issues)
[![Last Commit](https://img.shields.io/github/last-commit/SakuraMathcraft/QueScript?style=for-the-badge)](https://github.com/SakuraMathcraft/QueScript/commits/main)
[![License](https://img.shields.io/github/license/SakuraMathcraft/QueScript?style=for-the-badge)](LICENSE)

</div>

---

## 项目概览

QueScript 面向“**全流程问卷仿真 + 测量质量评估**”场景，强调离线运行与可复现：

- 文本问卷快速生成 HTML 页面
- 智能批量模拟（跳题、分支、偏好倾向、潜变量）
- 题级与结构级分析（Alpha、KMO/Bartlett、CR、CITC、EFA、CFA/Omega）
- 审计与复现产物输出（`config.json`、`path_log.csv`、`analysis_meta.json`）

## 界面截图
### GUI 主界面/>

### 报告示例

<img width="1919" height="1018" alt="问卷模拟大师" src="https://github.com/user-attachments/assets/b5e01d78-f95d-40d8-8b0a-8f41aba5853f" />

## 快速开始

```powershell
git clone https://github.com/SakuraMathcraft/QueScript.git
cd QueScript
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python mock_survey\gui_launcher.py
```

Windows 双击方式：

```powershell
cd mock_survey
run_gui.bat
```
## Star 趋势

<a href="https://star-history.com/#SakuraMathcraft/QueScript&Date" target="_blank">
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=SakuraMathcraft/QueScript&type=Date" />
</a>

## 功能矩阵

| 模块 | 能力说明 |
|---|---|
| 问卷生成 | 将问卷文本解析为 `index.html` |
| 智能模拟 | 批量填写、分支跳题、作答倾向与潜变量控制 |
| 统计分析 | 信效度、区分度、EFA/CFA、分支感知分析 |
| 审计复现 | `run_id + seed + 配置快照 + 路径日志 + 分析快照` |
| 打包发布 | Windows 离线打包（PyInstaller + 安装脚本） |
## 离线打包（Windows）

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -LocalChromeZip ".\chrome-win64.zip"
```

## 项目结构

- `mock_survey/`: GUI、模拟核心、统计分析、问卷生成
- `packaging/`: 打包脚本、安装器配置、PyInstaller 规范
- `docs/images/`: README 截图资源
- `requirements.txt`: 运行依赖

## 复现产物说明

每次模拟后，问卷目录中会生成：

- `survey_data_collected.csv`: 采集结果
- `config.json`: 模拟参数快照
- `path_log.csv`: 样本访问轨迹与跳转原因
- `analysis_meta.json`: 分析口径、门槛、纳入题项与签名

## 使用建议

- 建议样本量 `n >= 100`，结构分析更稳定
- 分支较强的问卷，优先查看分层分析结论
- 每个潜变量维度建议至少 3 道可比题项
- 覆盖率口径适合业务分析，严格公共题口径适合保守对比

## Roadmap

- 多分支结构诊断进一步增强
- 报告导出模板与可视化增强
- 跨平台打包能力完善

## Contributing

欢迎 Issue 和 PR：

1. 提供可复现问题描述
2. 附上输入样本与预期行为
3. 需要时附带 `config.json`、`path_log.csv`、`analysis_meta.json`

## English (Collapsible)

<details>
<summary>Click to expand English README</summary>

### Overview

QueScript is a local-first toolkit for **auditable survey simulation and measurement analysis**.

- Generate HTML surveys from plain questionnaire text
- Run branch-aware batch simulation with skip logic and response tendencies
- Evaluate data quality with Alpha, KMO/Bartlett, CR, CITC, EFA, CFA/Omega
- Preserve reproducibility artifacts (`config.json`, `path_log.csv`, `analysis_meta.json`)

### Quick Start

```powershell
git clone https://github.com/SakuraMathcraft/QueScript.git
cd QueScript
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python mock_survey\gui_launcher.py
```

### Offline Packaging (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -LocalChromeZip ".\chrome-win64.zip"
```

### Screenshots

- GUI Main: `docs/images/gui-main.svg`
- Report Sample: `docs/images/report-sample.svg`

</details>

## License

MIT License. See `LICENSE`.
