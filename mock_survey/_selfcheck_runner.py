from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import survey_generator as sg
from statistical_core import StatAnalyzer


def main():
    data = sg.parse_survey("mock_survey/survey_data.txt")
    sg.generate_html(data, "mock_survey/index.html")
    html = Path("mock_survey/index.html").read_text(encoding="utf-8")

    df = StatAnalyzer.generate_correlated_data(
        50,
        6,
        reliability="high",
        validity="high",
        n_factors=2,
        random_state=7,
    )
    efa = StatAnalyzer.run_efa_suite(df, n_factors=2)

    jump_needle = 'data-jump-target=' + chr(34) + '29' + chr(34)

    lines = [
        "runner_version=2",
        f"questions={len(data)}",
        f"jump_attr={(jump_needle in html)}",
        f"alpha={StatAnalyzer.calculate_cronbach_alpha(df):.3f}",
        f"kmo={StatAnalyzer.calculate_kmo(df):.3f}",
        f"efa_factors={efa['n_factors_used']}",
    ]
    Path("mock_survey/_selfcheck.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
