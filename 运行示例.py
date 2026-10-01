"""Generate clearly labelled sample files and build actual packages."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from pandao_delivery.core import build, summary


def create_sample(root, total=3):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    projects = [f"P{i:03d}" for i in range(1, total + 1)]
    recipe = {"schema": 1,
              "filename_pattern": r"(?P<project>[^_]+)_(?P<kind>[^_]+)_(?P<slot>[^_]+)_v(?P<version>\d+)\.[^.]+",
              "projects": projects,
              "items": [{"kind": "design", "label": {"zh": "设计文件", "en": "Design"}, "extensions": [".svg"], "min_count": 1, "max_count": 1},
                        {"kind": "guide", "label": {"zh": "说明文件", "en": "Guide"}, "extensions": [".txt"], "min_count": 1, "max_count": 1},
                        {"kind": "image", "label": {"zh": "配图", "en": "Images"}, "extensions": [".svg"], "min_count": 2, "max_count": 2}]}
    for i, project in enumerate(projects):
        folder = root / project
        folder.mkdir(exist_ok=True)
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200"><rect width="320" height="200" fill="#d8edf3"/><text x="30" y="100">Sample ' + project + '</text></svg>'
        (folder / f"{project}_design_main_v1.svg").write_text(svg.replace("Sample", "Old sample"), encoding="utf-8")
        (folder / f"{project}_design_main_v2.svg").write_text(svg, encoding="utf-8")
        for slot in ["front", "back"]:
            (folder / f"{project}_image_{slot}_v1.svg").write_text(svg.replace("Sample", slot), encoding="utf-8")
        if i % 6 != 1:
            (folder / f"{project}_guide_main_v1.txt").write_text("模拟说明 / Sample guide\n" + project, encoding="utf-8")
        if i % 6 == 2:
            copy = folder / "另一份"
            copy.mkdir(exist_ok=True)
            (copy / f"{project}_design_main_v2.svg").write_text(svg.replace("Sample", "Different sample"), encoding="utf-8")
    return recipe


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    recipe = create_sample(here / "demo-input")
    (here / "demo-recipe.json").write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")
    result = build(here / "demo-input", recipe, here / "demo-output")
    print(summary(result["report"]), end="")
    print("示例交付包已保存：" + result["directory"])
