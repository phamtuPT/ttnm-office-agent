import json
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval"


def test_eval_cases_are_well_formed():
    """Bộ ~100 yêu cầu đánh giá (đề xuất mục 7): id không trùng, tệp đầu vào có thật, kiểu kiểm tra được hỗ trợ."""
    from eval.run_eval import make_inputs

    cases = json.loads((EVAL / "cases.json").read_text(encoding="utf-8"))
    src = (EVAL / "run_eval.py").read_text(encoding="utf-8")
    builders = make_inputs()
    assert len(cases) >= 100
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["request"].strip() and c["checks"], c["id"]
        assert all(k in builders for k in c["inputs"]), c["id"]
        for ch in c["checks"]:
            assert f'"{ch["type"]}"' in src, f'{c["id"]}: chưa hỗ trợ kiểu kiểm tra {ch["type"]}'


def test_eval_inputs_build():
    from eval.run_eval import make_inputs
    for build in make_inputs().values():
        name, data = build()
        assert name.rsplit(".", 1)[1] in ("xlsx", "docx", "pptx") and len(data) > 1000
