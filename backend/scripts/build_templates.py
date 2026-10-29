"""Dựng lại mẫu slide trong app/resources/templates/ (chạy khi đổi thiết kế mẫu trong app/tools/pptx_design.py).

    python scripts/build_templates.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.tools.pptx_design import BUILT_IN, build_template  # noqa: E402

build_template(BUILT_IN["default_theme"], accent=True)
build_template(BUILT_IN["default_plain"], accent=False)
for name, path in BUILT_IN.items():
    print(f"{name}: {path} ({path.stat().st_size // 1024} KB)")
