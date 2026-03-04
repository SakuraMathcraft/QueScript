import os
import random
import time
from playwright.sync_api import sync_playwright

def run_smart_bot():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "index.html")
    file_url = f"file:///{file_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        print(f"Opening: {file_url}")
        page.goto(file_url)

        # 1. Identify all question containers
        questions = page.query_selector_all(".question")
        print(f"Found {len(questions)} questions.")

        for i, q in enumerate(questions):
            q_id = q.get_attribute("id")
            q_type = q.get_attribute("data-type")
            print(f"Processing {q_id} ({q_type})...")

            try:
                if q_type == "radio":
                    # Find all radio inputs in this question
                    radios = q.query_selector_all("input[type='radio']")
                    if radios:
                        choice = random.choice(radios)
                        val = choice.get_attribute("value")
                        choice.check()
                        print(f"  -> Selected radio: {val}")

                elif q_type == "checkbox":
                    checkboxes = q.query_selector_all("input[type='checkbox']")
                    if checkboxes:
                        # Select 1 to N random options
                        k = random.randint(1, len(checkboxes))
                        choices = random.sample(checkboxes, k)
                        for c in choices:
                            c.check()
                            print(f"  -> Checked: {c.get_attribute('value')}")

                elif q_type == "text":
                    textarea = q.query_selector("textarea")
                    if textarea:
                        textarea.fill("这是一个自动生成的测试回答。")
                        print("  -> Filled text area")

                elif q_type == "sort":
                    inputs = q.query_selector_all("input[type='number']")
                    # Assign random unique ranks
                    if inputs:
                        ranks = list(range(1, len(inputs) + 1))
                        random.shuffle(ranks)
                        for idx, inp in enumerate(inputs):
                            inp.fill(str(ranks[idx]))
                        print(f"  -> Filled sort ranks: {ranks}")

                elif q_type == "scale_radio":
                    radios = q.query_selector_all("input[type='radio']")
                    if radios:
                        choice = random.choice(radios)
                        choice.check()
                        print(f"  -> Selected scale: {choice.get_attribute('value')}")

                elif q_type == "matrix":
                    # Find table rows
                    rows = q.query_selector_all("tbody tr")
                    for row in rows:
                        radios = row.query_selector_all("input[type='radio']")
                        if radios:
                            choice = random.choice(radios)
                            choice.check()
                    print(f"  -> Filled {len(rows)} matrix rows")

            except Exception as e:
                print(f"Error processing question {q_id}: {e}")

        # Submit
        print("Submitting...")
        page.on("dialog", lambda d: print(f"Alert: {d.message}") or d.accept())

        # Check if submit button exists
        if page.query_selector("#submitBtn"):
            page.click("#submitBtn")
        else:
            print("Submit button not found!")

        time.sleep(3)
        browser.close()
        print("Smart simulation finished.")

if __name__ == "__main__":
    run_smart_bot()
