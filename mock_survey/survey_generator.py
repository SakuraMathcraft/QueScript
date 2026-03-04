import re
import os

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode('gbk', errors='replace').decode('gbk')) # Try to safe print for windows console
        except:
            pass # Just ignore if we can't print

def _extract_scale_options(scale_line):
    """Extract numeric options from lines like: |不可能|○0|○1|...|极有可能|"""
    if "○" not in scale_line:
        return []
    parts = [p.strip() for p in scale_line.strip("|").split("|")]
    options = []
    for part in parts:
        if part.startswith("○"):
            value = part.replace("○", "").strip()
            if value:
                options.append(value)
    return options

def _extract_jump_target(text):
    """Extract jump target question id from option text like '请跳至第25题'."""
    m = re.search(r"跳至第\s*(\d+)\s*题", text)
    return m.group(1) if m else ""


def _extract_option_value(option_text):
    # Keep existing A./B. style values compact for CSV readability.
    return option_text.split('.', 1)[0].strip() if '.' in option_text else option_text.strip()

def parse_survey(file_path):
    # Try different encodings
    encodings = ["utf-8", "gbk", "gb18030", "utf-16"]
    lines = []

    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [l.strip() for l in f.readlines()]
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f.readlines()]

    survey_data = []
    current_question = None

    for i, line in enumerate(lines):
        if not line:
            continue

        # Skip section titles like 【消费者画像】
        if line.startswith("【") and line.endswith("】"):
            continue

        # Question title: 1. xxx
        match_question = re.match(r"^(\d+)\.\s*(.*)", line)
        if match_question:
            q_text = match_question.group(2)
            # Skip non-question numbered instructions at the top of txt files
            if "【" not in q_text or "】" not in q_text:
                continue

            if current_question:
                # Ensure matrix has usable headers
                if current_question["type"] == "matrix" and not current_question["headers"]:
                    current_question["headers"] = ["1", "2", "3", "4", "5"]
                survey_data.append(current_question)

            q_id = match_question.group(1)
            q_text = match_question.group(2)

            q_type = "unknown"
            if "【单选题】" in q_text:
                q_type = "radio"
            elif "【多选题】" in q_text:
                q_type = "checkbox"
            elif "【排序题】" in q_text:
                q_type = "sort"
            elif "【填空题】" in q_text or "____" in q_text:
                q_type = "text"
            elif "【矩阵量表题】" in q_text:
                q_type = "matrix"
            elif "【量表题】" in q_text:
                q_type = "scale"

            # Heuristic: scale line often appears right after question
            if q_type == "unknown":
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if "|" in next_line and "○" in next_line:
                    q_type = "scale"

            current_question = {
                "id": q_id,
                "text": q_text,
                "type": q_type,
                "options": [],
                "rows": [],
                "headers": [],
            }
            continue

        if not current_question:
            continue

        # Matrix parsing (supports markdown and plain text matrix rows)
        if current_question["type"] == "matrix":
            # Markdown header/rows
            if line.startswith("|"):
                parts = [p.strip() for p in line.strip("|").split("|")]
                if "评价维度" in parts:
                    current_question["headers"] = [re.sub(r".*\((\d+)\).*", r"\1", p) for p in parts[1:]]
                elif "----" not in line and parts:
                    current_question["rows"].append(parts[0])
                continue

            # Plain text matrix header: 评价维度 非常不满意（1） ...
            if "评价维度" in line and "（" in line and "）" in line:
                nums = re.findall(r"（(\d+)）", line)
                if nums:
                    current_question["headers"] = nums
                continue

            # Plain text matrix row: 外观包装 ○1 ○2 ○3 ○4 ○5
            if "○" in line:
                row_name = line.split("○", 1)[0].strip()
                if row_name:
                    current_question["rows"].append(row_name)
                if not current_question["headers"]:
                    count = len(re.findall(r"○\d+", line))
                    if count > 0:
                        current_question["headers"] = [str(x) for x in range(1, count + 1)]
                continue

            continue

        # Scale parsing
        if current_question["type"] == "scale":
            if "|" in line and "○" in line:
                options = _extract_scale_options(line)
                if options:
                    current_question["options"] = options
                    current_question["type"] = "scale_radio"
            continue

        # Standard options
        if line.startswith("○"):
            if current_question["type"] == "unknown":
                current_question["type"] = "radio"
            current_question["options"].append(line[1:].strip())
        elif line.startswith("□"):
            if current_question["type"] == "unknown":
                current_question["type"] = "checkbox"
            current_question["options"].append(line[1:].strip())
        elif line.startswith("[ ]"):
            if current_question["type"] == "unknown":
                current_question["type"] = "sort"
            current_question["options"].append(line[3:].strip())

    if current_question:
        if current_question["type"] == "matrix" and not current_question["headers"]:
            current_question["headers"] = ["1", "2", "3", "4", "5"]
        survey_data.append(current_question)

    return survey_data

def generate_html(survey_data, output_file):
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>自贡冷吃兔消费市场调研问卷</title>
    <style>
        body { font-family: "Microsoft YaHei", sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; background: #f0f2f5; }
        .container { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        .section-header { margin-top: 30px; border-left: 5px solid #0095ff; padding-left: 10px; color: #0095ff; }
        .question { margin-bottom: 25px; padding: 15px; border-bottom: 1px dashed #eee; }
        .question-title { font-weight: bold; margin-bottom: 10px; font-size: 16px; }
        .option { margin: 5px 0; display: block; cursor: pointer; }
        input[type="text"], textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
        th { background: #fafafa; }
        .btn-submit { display: block; width: 100%; padding: 15px; background: #0095ff; color: white; border: none; border-radius: 4px; font-size: 18px; cursor: pointer; margin-top: 30px; }
        .btn-submit:hover { background: #0077cc; }
        .scale-container { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
        .scale-item { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>自贡冷吃兔消费市场调研问卷</h1>
        <form id="surveyForm">
    """

    for item in survey_data:
        if item.get("type") == "section":
            html_content += f'<h2 class="section-header">{item["title"]}</h2>'
            continue

        q_id = item["id"]
        q_text = item["text"]
        q_type = item["type"]

        html_content += f'<div class="question" id="q{q_id}" data-qid="{q_id}" data-type="{q_type}">'
        html_content += f'<div class="question-title">{q_id}. {q_text}</div>'

        if q_type == "radio":
            for opt in item["options"]:
                val = _extract_option_value(opt)
                jump_target = _extract_jump_target(opt)
                jump_attr = f' data-jump-target="{jump_target}"' if jump_target else ""
                html_content += f'<label class="option"><input type="radio" name="q{q_id}" value="{val}"{jump_attr}> {opt}</label>'
                if "____" in opt or "请填写" in opt:
                     html_content += f'<input type="text" name="q{q_id}_other" placeholder="请注明" style="display:none; width: 50%; display: inline-block; margin-left: 10px;">'

        elif q_type == "checkbox":
            for opt in item["options"]:
                val = _extract_option_value(opt)
                jump_target = _extract_jump_target(opt)
                jump_attr = f' data-jump-target="{jump_target}"' if jump_target else ""
                html_content += f'<label class="option"><input type="checkbox" name="q{q_id}" value="{val}"{jump_attr}> {opt}</label>'
                if "____" in opt or "请填写" in opt:
                     html_content += f'<input type="text" name="q{q_id}_other" placeholder="请注明" style="display:none; width: 50%; display: inline-block; margin-left: 10px;">'

        elif q_type == "text":
            html_content += f'<textarea name="q{q_id}" rows="4"></textarea>'

        elif q_type == "sort":
            html_content += '<div class="sort-instruction" style="font-size: 12px; color: #666; margin-bottom: 5px;">请在框中输入序号(1代表最重要)</div>'
            for opt in item["options"]:
                val = _extract_option_value(opt)
                html_content += f'<div class="option" style="display: flex; align-items: center;"><input type="number" name="q{q_id}_{val}" min="1" max="{len(item["options"])}" style="width: 50px; margin-right: 10px;"> {opt}</div>'

        elif q_type == "scale_radio":
            html_content += '<div class="scale-container">'
            html_content += '<span>不可能</span>'
            for opt in item["options"]:
                html_content += f'<div class="scale-item"><label><br><input type="radio" name="q{q_id}" value="{opt}"><br>{opt}</label></div>'
            html_content += '<span>极有可能</span>'
            html_content += '</div>'

        elif q_type == "matrix":
            html_content += '<table><thead><tr><th>评价维度</th>'
            for h in item["headers"]:
                html_content += f'<th>{h}</th>'
            html_content += '</tr></thead><tbody>'

            for i, row in enumerate(item["rows"]):
                html_content += f'<tr><td>{row}</td>'
                for h_idx, h in enumerate(item["headers"]):
                     # Using a unique name for each row in matrix: q21_row0, q21_row1...
                    html_content += f'<td><input type="radio" name="q{q_id}_row{i}" value="{h_idx+1}"></td>'
                html_content += '</tr>'
            html_content += '</tbody></table>'

        html_content += '</div>'

    html_content += """
        <button type="submit" class="btn-submit" id="submitBtn">提交问卷</button>
        </form>
    </div>
    <script>
        document.getElementById('surveyForm').addEventListener('submit', function(e) {
            e.preventDefault();
            alert('模拟提交成功！');
            console.log('Form Submitted');
        });
        
        // Simple logic to show 'other' input
        const inputs = document.querySelectorAll('input[type="radio"], input[type="checkbox"]');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                // Find sibling text input if exists
                const parent = this.closest('.option');
                if(!parent) return;
                
                // This logic is simplified; in real scenario, we need to check if "Other" is selected
                // For now, we omit specific dynamic show/hide for simplicity in mock
            });
        });
    </script>
</body>
</html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    # print(f"Generated {output_file}") # Removed or use safe_print

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "survey_data.txt")
    output_file = os.path.join(current_dir, "index.html")

    data = parse_survey(input_file)
    generate_html(data, output_file)
