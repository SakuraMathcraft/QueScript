import json
import os
import re


def _extract_scale_options(scale_line):
    if "○" not in scale_line:
        return []
    parts = [p.strip() for p in scale_line.strip("|").split("|")]
    out = []
    for p in parts:
        if p.startswith("○"):
            v = p.replace("○", "").strip()
            if v:
                out.append(v)
    return out


def _extract_jump_target(text):
    m = re.search(r"跳至第\s*(\d+)\s*题", text or "")
    return m.group(1) if m else ""


def _extract_option_value(option_text):
    return option_text.split(".", 1)[0].strip() if "." in option_text else option_text.strip()


def _normalize_text_markers(text):
    return (text or "").replace("[", "【").replace("]", "】")


def _detect_question_type(text):
    t = _normalize_text_markers(text)
    if "【单选题】" in t:
        return "radio"
    if "【多选题】" in t:
        return "checkbox"
    if "【排序题】" in t:
        return "sort"
    if "【填空题】" in t or "____" in t:
        return "text"
    if "【矩阵量表题】" in t:
        return "matrix"
    if "【量表题】" in t:
        return "scale"
    return "unknown"


def _strip_question_markers(text):
    t = _normalize_text_markers(text)
    t = re.sub(r"【(单选题|多选题|排序题|填空题|矩阵量表题|量表题)】", "", t)
    t = re.sub(r"\*+", "", t)
    return t.strip()


def extract_survey_title(file_path):
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

    for line in lines:
        if not line:
            continue
        if line.startswith("###") or line.startswith("##"):
            return line.lstrip("#").strip()
        if line.startswith("【") and line.endswith("】"):
            continue
        if line.startswith("填写说明"):
            continue
        if line.startswith("1.") or line.startswith("1、"):
            continue
        return line

    return os.path.splitext(os.path.basename(file_path))[0]


def _parse_dependency_rule(line):
    txt = (line or "").strip()
    if not txt.startswith("依赖于"):
        return None
    m = re.search(r"依赖于[（\(]\s*题目[:：]\s*(.+)[）\)]\s*第\s*([\d;；,，\s]+)\s*个选项", txt)
    if not m:
        return None
    q_text = re.sub(r"[.。…]+$", "", m.group(1).strip())
    idx = []
    for token in re.split(r"[;；,，\s]+", m.group(2)):
        if token.isdigit():
            idx.append(int(token))
    return {"source_text": q_text, "source_option_indices": sorted(set(i for i in idx if i > 0))}


def _resolve_dependency_rules(survey_data):
    def norm(s):
        return re.sub(r"\s+", "", (s or ""))

    for q in survey_data:
        rule = q.get("show_if")
        if not rule:
            continue
        src_key = norm(rule.get("source_text", ""))
        src = None
        for cand in survey_data:
            t = norm(cand.get("text", ""))
            if src_key and (src_key in t or t in src_key):
                src = cand
                break

        if not src:
            q["show_if"] = None
            continue

        allowed = []
        opts = src.get("options", [])
        for i in rule.get("source_option_indices", []):
            pos = i - 1
            if 0 <= pos < len(opts):
                allowed.append(_extract_option_value(opts[pos]))

        q["show_if"] = {
            "source_qid": str(src.get("id", "")),
            "allowed_values": allowed,
            "source_option_indices": rule.get("source_option_indices", []),
            "source_text": src.get("text", ""),
        }


def parse_survey(file_path):
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
    next_auto_id = 1
    pending_show_if = None

    def finalize_question(q):
        if not q:
            return
        if q["type"] == "matrix" and not q["headers"]:
            q["headers"] = ["1", "2", "3", "4", "5"]
        survey_data.append(q)

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        normalized = _normalize_text_markers(line)
        if normalized.startswith("【") and normalized.endswith("】"):
            continue

        dep = _parse_dependency_rule(normalized)
        if dep:
            pending_show_if = dep
            continue

        m_question = re.match(r"^(\d+)\s*[.、)]\s*(.*)", line)
        if m_question:
            q_id = m_question.group(1)
            q_text_raw = m_question.group(2).strip()
            q_type = _detect_question_type(q_text_raw)
            q_text = _strip_question_markers(q_text_raw)

            if q_type == "unknown" and ("填写说明" in q_text or "题目" in q_text):
                continue

            finalize_question(current_question)
            current_question = {
                "id": q_id,
                "text": q_text,
                "type": q_type,
                "options": [],
                "rows": [],
                "headers": [],
                "show_if": pending_show_if,
            }
            pending_show_if = None
            next_auto_id = max(next_auto_id, int(q_id) + 1)
            continue

        if _detect_question_type(normalized) != "unknown" and not line.startswith(("○", "□", "[ ]")):
            q_text = _strip_question_markers(line)
            if not q_text:
                # Standalone marker line, already handled by previous stem+next-line rule.
                continue
            finalize_question(current_question)
            current_question = {
                "id": str(next_auto_id),
                "text": q_text,
                "type": _detect_question_type(normalized),
                "options": [],
                "rows": [],
                "headers": [],
                "show_if": pending_show_if,
            }
            pending_show_if = None
            next_auto_id += 1
            continue

        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if (
            not line.startswith(("○", "□", "[ ]", "|"))
            and _detect_question_type(next_line) != "unknown"
            and _detect_question_type(line) == "unknown"
        ):
            finalize_question(current_question)
            current_question = {
                "id": str(next_auto_id),
                "text": line,
                "type": _detect_question_type(next_line),
                "options": [],
                "rows": [],
                "headers": [],
                "show_if": pending_show_if,
            }
            pending_show_if = None
            next_auto_id += 1
            continue

        if not current_question:
            continue

        if current_question["type"] == "matrix":
            if line.startswith("|"):
                parts = [p.strip() for p in line.strip("|").split("|")]
                if "评价维度" in parts:
                    current_question["headers"] = [re.sub(r".*\((\d+)\).*", r"\1", p) for p in parts[1:]]
                elif "----" not in line and parts:
                    current_question["rows"].append(parts[0])
                continue
            if "○" in line:
                if "评价维度" in line or (not current_question["headers"] and line.count("○") >= 3 and "同意" in line):
                    current_question["headers"] = [str(x) for x in range(1, line.count("○") + 1)]
                    continue
                row_name = line.split("○", 1)[0].strip()
                if row_name:
                    current_question["rows"].append(row_name)
                    if not current_question["headers"]:
                        current_question["headers"] = [str(x) for x in range(1, line.count("○") + 1)]
                continue
            continue

        if current_question["type"] in ("scale", "radio", "unknown") and not line.startswith(("○", "□", "[ ]")):
            if ("|" in line and "○" in line) or re.search(r"○\s*\d+", line):
                opts = _extract_scale_options(line) or re.findall(r"○\s*(\d+)", line)
                if opts:
                    current_question["options"] = opts
                    current_question["type"] = "scale_radio"
                    continue

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

    finalize_question(current_question)
    _resolve_dependency_rules(survey_data)
    return survey_data


def generate_html(survey_data, output_file, survey_title=None):
    title = (survey_title or "问卷调查").strip() or "问卷调查"
    html_content = f"""
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <title>{title}</title>
    <style>
        body {{ font-family: \"Microsoft YaHei\", sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; background: #f0f2f5; }}
        .container {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ text-align: center; color: #333; }}
        .question {{ margin-bottom: 25px; padding: 15px; border-bottom: 1px dashed #eee; }}
        .question-title {{ font-weight: bold; margin-bottom: 10px; font-size: 16px; }}
        .option {{ margin: 5px 0; display: block; cursor: pointer; }}
        input[type=\"text\"], textarea {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
        th {{ background: #fafafa; }}
        .btn-submit {{ display: block; width: 100%; padding: 15px; background: #0095ff; color: white; border: none; border-radius: 4px; font-size: 18px; cursor: pointer; margin-top: 30px; }}
        .btn-submit:hover {{ background: #0077cc; }}
        .scale-container {{ display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }}
        .scale-item {{ text-align: center; }}
    </style>
</head>
<body>
    <div class=\"container\">
        <h1>{title}</h1>
        <form id=\"surveyForm\">
    """

    for item in survey_data:
        q_id = item["id"]
        q_text = item["text"]
        q_type = item["type"]

        show_if = item.get("show_if")
        show_if_attr = ""
        if show_if and show_if.get("source_qid") and show_if.get("allowed_values"):
            show_if_attr = f" data-show-if='{json.dumps(show_if, ensure_ascii=False)}'"

        html_content += f'<div class="question" id="q{q_id}" data-qid="{q_id}" data-type="{q_type}"{show_if_attr}>'
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
            html_content += '<div class="scale-container"><span>不可能</span>'
            for opt in item["options"]:
                html_content += f'<div class="scale-item"><label><br><input type="radio" name="q{q_id}" value="{opt}"><br>{opt}</label></div>'
            html_content += '<span>极有可能</span></div>'

        elif q_type == "matrix":
            html_content += '<table><thead><tr><th>评价维度</th>'
            for h in item["headers"]:
                html_content += f'<th>{h}</th>'
            html_content += '</tr></thead><tbody>'
            for i, row in enumerate(item["rows"]):
                html_content += f'<tr><td>{row}</td>'
                for h_idx, _ in enumerate(item["headers"]):
                    html_content += f'<td><input type="radio" name="q{q_id}_row{i}" value="{h_idx+1}"></td>'
                html_content += '</tr>'
            html_content += '</tbody></table>'

        html_content += '</div>'

    html_content += """
        <button type="submit" class="btn-submit" id="submitBtn">提交问卷</button>
        </form>
    </div>
    <script>
        function parseShowIf(el) {
            const raw = el.getAttribute('data-show-if');
            if (!raw) return null;
            try { return JSON.parse(raw); } catch (_) { return null; }
        }

        function getAnsweredValues(sourceQid) {
            const values = [];
            const selected = document.querySelectorAll('input[name="q' + sourceQid + '"]:checked');
            selected.forEach(x => values.push((x.value || '').trim()));
            return values;
        }

        function refreshVisibility() {
            document.querySelectorAll('.question').forEach(q => {
                const rule = parseShowIf(q);
                if (!rule) {
                    q.style.display = '';
                    return;
                }
                const selected = getAnsweredValues(rule.source_qid || '');
                const allowed = (rule.allowed_values || []).map(v => String(v).trim());
                const show = selected.some(v => allowed.includes(v));
                q.style.display = show ? '' : 'none';
            });
        }

        document.addEventListener('change', refreshVisibility);
        document.addEventListener('DOMContentLoaded', refreshVisibility);

        document.getElementById('surveyForm').addEventListener('submit', function(e) {
            e.preventDefault();
            alert('模拟提交成功！');
            console.log('Form Submitted');
        });
    </script>
</body>
</html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "survey_data.txt")
    output_file = os.path.join(current_dir, "index.html")
    data = parse_survey(input_file)
    generate_html(data, output_file, survey_title=extract_survey_title(input_file))
