import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from pandao_delivery.core import DeliveryError, build, digest, inventory, plan, safe_name, validate_recipe, verify_archive

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sample", ROOT / "运行示例.py")
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "input"
    recipe = sample.create_sample(source)
    return source, recipe, tmp_path / "output"


def test_sample_produces_only_complete_packages_and_preserves_sources(case):
    source, recipe, output = case
    originals = {str(p.relative_to(source)): digest(p) for p in source.rglob("*") if p.is_file()}
    result = build(source, recipe, output)
    folder = Path(result["directory"])
    assert sorted(p.name for p in folder.glob("*.zip")) == ["P001.zip"]
    assert [p["ready"] for p in result["report"]["projects"]] == [True, False, False]
    assert verify_archive(folder / "P001.zip") == {"passed": True, "project": "P001", "files": 4}
    assert {str(p.relative_to(source)): digest(p) for p in source.rglob("*") if p.is_file()} == originals
    assert "ready: 1; blocked: 2" in (folder / "Summary.en.txt").read_text(encoding="utf-8")
    assert "資料" not in (folder / "Summary.en.txt").read_text(encoding="utf-8")


def test_bulk_sixty_projects_all_totals_and_archive_contents(case):
    source, _, output = case
    # Use a new independent folder so earlier sample files cannot change totals.
    bulk = source.parent / "bulk"
    recipe = sample.create_sample(bulk, 60)
    result = build(bulk, recipe, output)
    report = result["report"]
    assert len(report["projects"]) == 60
    assert sum(p["ready"] for p in report["projects"]) == 40
    assert sum(any(i["code"] == "conflict" for i in p["issues"]) for p in report["projects"]) == 10
    assert sum(any(i["code"] == "missing" and i["kind"] == "guide" for i in p["issues"]) for p in report["projects"]) == 10
    archives = list(Path(result["directory"]).glob("*.zip"))
    assert len(archives) == 40
    assert sum(verify_archive(p)["files"] for p in archives) == 160


def test_numeric_versions_and_identical_duplicates(case):
    source, recipe, _ = case
    main = source / "P001/P001_design_main_v2.svg"
    newest = main.with_name("P001_design_main_v10.svg")
    newest.write_bytes(b"latest")
    duplicate = source / "copy"
    duplicate.mkdir()
    (duplicate / newest.name).write_bytes(newest.read_bytes())
    project = plan(source, recipe)["projects"][0]
    selected = [p for p in project["files"] if p["kind"] == "design"]
    assert project["ready"] and len(selected) == 1 and selected[0]["version"] == 10
    assert len(project["discarded"]) == 3


def test_missing_whole_project_is_reported(case):
    source, recipe, _ = case
    recipe["projects"].append("P404")
    project = plan(source, recipe)["projects"][-1]
    assert not project["ready"] and len(project["issues"]) == 3


def test_unknown_files_extensions_and_projects_are_ignored(case):
    source, recipe, _ = case
    for name in ["notes.txt", "P001_design_extra_v9.exe", "OUT_design_main_v9.svg"]:
        (source / name).write_text("not required", encoding="utf-8")
    result = plan(source, recipe)
    assert {x["reason"] for x in result["ignored"]} == {"unmatched", "extension", "outside_recipe"}
    assert result["projects"][0]["ready"]


def test_overfull_category_blocks_project(case):
    source, recipe, _ = case
    (source / "P001/P001_design_extra_v1.svg").write_text("extra", encoding="utf-8")
    assert any(i["code"] == "excess" for i in plan(source, recipe)["projects"][0]["issues"])


@pytest.mark.parametrize("name", ["../x", "/tmp", "C:x", "a/b", "a\\b", "CON", "nul.txt", "..", "", "bad."])
def test_output_names_cannot_escape_or_use_reserved_paths(name):
    with pytest.raises(DeliveryError):
        safe_name(name)


@pytest.mark.parametrize("change", [
    {"schema": 9}, {"projects": []}, {"projects": ["a", "a"]}, {"projects": ["a", "A"]},
    {"projects": [{}]}, {"filename_pattern": "("}, {"filename_pattern": r".*"}, {"items": []},
    {"items": [{"kind": "x", "extensions": [".txt"], "min_count": 3, "max_count": 1}]},
    {"items": [{"kind": "x", "extensions": ["exe"]}]}
])
def test_bad_recipes_are_rejected(case, change):
    _, recipe, _ = case
    recipe.update(change)
    with pytest.raises(DeliveryError):
        validate_recipe(recipe)


@pytest.mark.parametrize("where", ["same", "inside", "ancestor"])
def test_input_output_directory_overlap_rejected(case, where):
    source, recipe, _ = case
    output = source if where == "same" else source / "output" if where == "inside" else source.parent
    with pytest.raises(DeliveryError):
        build(source, recipe, output)


def test_repeat_does_not_duplicate_or_overwrite_packages(case):
    source, recipe, output = case
    first = build(source, recipe, output)
    archive = Path(first["directory"]) / "P001.zip"
    sha, modified = digest(archive), archive.stat().st_mtime_ns
    second = build(source, recipe, output)
    assert second["reused"] and second["directory"] == first["directory"]
    assert digest(archive) == sha and archive.stat().st_mtime_ns == modified


def test_modified_selection_invalidates_reviewed_plan(case):
    source, recipe, output = case
    before = plan(source, recipe)
    (source / "P001/P001_guide_main_v1.txt").write_text("modified", encoding="utf-8")
    with pytest.raises(DeliveryError):
        build(source, recipe, output, planned=before)
    assert not output.exists()


def test_new_source_version_creates_new_run_and_keeps_old(case):
    source, recipe, output = case
    first = build(source, recipe, output)
    (source / "P001/P001_guide_main_v2.txt").write_text("new guide", encoding="utf-8")
    second = build(source, recipe, output)
    assert first["directory"] != second["directory"]
    assert Path(first["directory"]).is_dir() and Path(second["directory"]).is_dir()


def test_tampered_archive_and_report_are_not_reused(case):
    source, recipe, output = case
    result = build(source, recipe, output)
    folder = Path(result["directory"])
    with zipfile.ZipFile(folder / "P001.zip", "a") as archive:
        archive.writestr("extra.txt", "unexpected")
    with pytest.raises(DeliveryError):
        build(source, recipe, output)
    with pytest.raises(DeliveryError):
        verify_archive(folder / "P001.zip")


def test_archive_content_mismatch_detected(case):
    source, recipe, output = case
    selected = plan(source, recipe)["projects"][0]
    manifest = inventory(selected)
    output.mkdir()
    archive_path = output / "broken.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("inventory.json", json.dumps(manifest))
        for x in manifest["files"]:
            archive.writestr(x["member"], "incorrect")
    with pytest.raises(DeliveryError):
        verify_archive(archive_path)


def test_unicode_names_preserved(case):
    source, recipe, output = case
    recipe["projects"] = ["客户甲"]
    folder = source / "客户甲"
    folder.mkdir()
    for kind, slot, ext in [("design", "main", "svg"), ("guide", "main", "txt"), ("image", "front", "svg"), ("image", "back", "svg")]:
        (folder / f"客户甲_{kind}_{slot}_v1.{ext}").write_text("原始中文资料", encoding="utf-8")
    result = build(source, recipe, output)
    with zipfile.ZipFile(Path(result["directory"]) / "客户甲.zip") as archive:
        assert archive.read("guide/客户甲_guide_main_v1.txt").decode("utf-8") == "原始中文资料"


def test_cli_partial_delivery_exit_and_english_help(case):
    source, recipe, output = case
    config = source.parent / "recipe.json"
    config.write_text(json.dumps(recipe), encoding="utf-8")
    run = subprocess.run([sys.executable, "-m", "pandao_delivery.cli", "--lang", "en", "build", "--source", str(source), "--recipe", str(config), "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 2 and "ready: 1; blocked: 2" in run.stdout
    help_result = subprocess.run([sys.executable, "-m", "pandao_delivery.cli", "--lang", "en", "--help"], capture_output=True, text=True, encoding="utf-8")
    assert help_result.returncode == 0 and "Assemble files" in help_result.stdout
    assert not any('\u4e00' <= c <= '\u9fff' for c in help_result.stdout)


def test_existing_lock_prevents_concurrent_run(case):
    source, recipe, output = case
    reviewed = plan(source, recipe)
    output.mkdir()
    lock = output / ("run-" + reviewed["fingerprint"][:16] + ".lock")
    lock.write_text("running", encoding="utf-8")
    with pytest.raises(DeliveryError):
        build(source, recipe, output)
    assert lock.exists()
