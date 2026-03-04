from pathlib import Path
import re

html = Path("mock_survey/index.html").read_text(encoding="utf-8")
scale = len(re.findall(r'data-type="scale_radio"', html))
matrix_blocks = len(re.findall(r'data-type="matrix"', html))
row_names = set(re.findall(r'name="(q24_row\d+)"', html))
rows = len(row_names)
print("scale_radio_questions=", scale)
print("matrix_questions=", matrix_blocks)
print("matrix_rows_q24=", rows)
print("total_scale_items_if_matrix_expanded=", scale + rows)
