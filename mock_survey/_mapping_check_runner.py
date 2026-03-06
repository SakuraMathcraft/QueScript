import json
import re
from pathlib import Path

import survey_generator as sg

base = Path(__file__).resolve().parent
txt = base / "问卷.txt"
html_path = base / "index.html"

data = sg.parse_survey(str(txt))
sg.generate_html(data, str(html_path), survey_title=sg.extract_survey_title(str(txt)))
html = html_path.read_text(encoding="utf-8", errors="replace") if html_path.exists() else ""
titles = re.findall(r'<div class="question-title">\s*\d+\.\s*(.*?)</div>', html)

out = {
    "parsed_count": len(data),
    "html_count": len(titles),
    "parsed_empty_text": [i + 1 for i, q in enumerate(data) if not str(q.get("text", "")).strip()],
    "html_empty_titles": [i + 1 for i, t in enumerate(titles) if not str(t).strip()],
    "parsed_preview": [{"id": q.get("id"), "type": q.get("type"), "text": q.get("text")} for q in data[:20]],
    "html_preview": titles[:20],
}

(base / "_mapping_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("done")
