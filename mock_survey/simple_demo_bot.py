import os
import random
import time
from playwright.sync_api import sync_playwright

def run_bot():
    # 获取 HTML 文件的绝对路径 (相对于脚本所在目录)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "index.html")
    file_url = f"file:///{file_path}"

    with sync_playwright() as p:
        # 1. 启动浏览器 (headless=False 可以看到浏览器界面)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        # 2. 打开本地网页
        print(f"正在打开: {file_url}")
        page.goto(file_url)

        # 3. 模拟填写逻辑

        # --- 问题 1: 单选 (随机选择) ---
        genders = ['male', 'female']
        chosen_gender = random.choice(genders)
        print(f"Q1 选择性别: {chosen_gender}")
        # 使用 CSS 选择器定位 input
        page.check(f"input[name='gender'][value='{chosen_gender}']")

        # --- 问题 2: 多选 (随机选择 1-3 个) ---
        langs = ['python', 'js', 'cpp']
        # 随机选取 1 到 len(langs) 个选项
        chosen_langs = random.sample(langs, k=random.randint(1, len(langs)))
        print(f"Q2 选择语言: {chosen_langs}")
        for lang in chosen_langs:
            page.check(f"input[name='lang'][value='{lang}']")

        # --- 问题 3: 填空 ---
        reasons = [
            "为了提高工作效率",
            "学习 Playwright 框架",
            "测试我的代码逻辑",
            "模拟用户行为"
        ]
        chosen_reason = random.choice(reasons)
        print(f"Q3 填写原因: {chosen_reason}")
        page.fill("textarea[name='reason']", chosen_reason)

        # 4. 提交
        print("点击提交按钮...")
        # 监听 dialog 事件 (alert 弹窗)
        page.on("dialog", lambda dialog: print(f"网页弹窗: {dialog.message}") or dialog.accept())

        page.click("#submitBtn")

        # 暂停几秒以便观察结果
        time.sleep(2)

        browser.close()
        print("模拟完成。")

if __name__ == "__main__":
    run_bot()
