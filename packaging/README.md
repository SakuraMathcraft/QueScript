# QueScript 打包说明（Windows）

本目录提供从源码构建可分发 GUI 应用与安装包的完整脚本。

## 文件说明

- `packaging/build_package.ps1`: 一键构建脚本（可选生成安装包）
- `packaging/quescript_gui.spec`: PyInstaller onedir 配置
- `packaging/playwright_runtime_hook.py`: 运行时设置 Playwright 浏览器路径与可写工作目录
- `packaging/installer.iss`: Inno Setup 安装包脚本

## 前置条件

1. Windows + PowerShell
2. 已创建虚拟环境（推荐 `E:\QueScript\.venv`）
3. 本地离线浏览器包：`chrome-win64.zip`（默认路径 `E:\QueScript\chrome-win64.zip`）
4. 安装 Inno Setup（仅在需要生成安装包时）

## 快速构建（仅可分发目录）

```powershell
cd E:\QueScript
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -LocalChromeZip "E:\QueScript\chrome-win64.zip"
```

输出目录：`dist\QueScriptSurvey\`

## 生成安装包（可选）

```powershell
cd E:\QueScript
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -BuildInstaller -LocalChromeZip "E:\QueScript\chrome-win64.zip"
```

输出目录：`installer_out\`

## 预检查（不构建）

```powershell
cd E:\QueScript
powershell -ExecutionPolicy Bypass -File .\packaging\build_package.ps1 -SkipBuild
```

## 验证清单

1. 运行 `dist\QueScriptSurvey\QueScriptSurvey.exe`
2. 在 GUI 中执行一次模拟，确认可生成：
   - `survey_data_collected.csv`
   - `config.json`
   - `path_log.csv`
3. 若使用安装包，安装后重复第 1~2 步

## 常见问题

- **提示缺少离线浏览器包**：确认 `-LocalChromeZip` 指向存在的 `chrome-win64.zip`。
- **提示 `chrome.exe` 不存在**：确认压缩包内结构为 `chrome-win64\chrome.exe`。
- **安装后无法写文件**：运行时钩子会切到 `%LOCALAPPDATA%\QueScriptSurvey`，请检查该目录权限。
- **iscc 不存在**：安装 Inno Setup 并确保 `iscc` 在 PATH 中。
