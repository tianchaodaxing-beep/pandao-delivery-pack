"""Independent implementation. Source files are only read, never moved."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile


class DeliveryError(ValueError):
    """An input or output requires a correction before packaging."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[\w.-]+", value) or value in {".", ".."}:
        raise DeliveryError("项目和类别只允许字母、数字、下划线、短横线和点 / Invalid project or item name")
    if value.endswith((".", " ")) or value.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))
    }:
        raise DeliveryError("名称不能是系统保留名称 / Reserved file name")
    return value


def validate_recipe(recipe):
    if not isinstance(recipe, dict) or recipe.get("schema") != 1:
        raise DeliveryError("交付清单需要 schema: 1 / Recipe requires schema: 1")
    try:
        pattern = re.compile(recipe["filename_pattern"])
    except (KeyError, TypeError, re.error) as exc:
        raise DeliveryError("文件名匹配规则无效 / Invalid filename pattern") from exc
    if not {"project", "kind", "version"}.issubset(pattern.groupindex):
        raise DeliveryError("匹配规则需要 project、kind、version / Pattern requires project, kind and version")
    projects = recipe.get("projects")
    if not isinstance(projects, list) or not projects or any(not isinstance(x, str) for x in projects):
        raise DeliveryError("请列出不重复的项目编号 / Provide unique project IDs")
    for project in projects:
        safe_name(project)
    if len(set(projects)) != len(projects) or len({x.casefold() for x in projects}) != len(projects):
        raise DeliveryError("项目编号不能重复 / Duplicate project IDs")
    items = recipe.get("items")
    if not isinstance(items, list) or not items:
        raise DeliveryError("交付清单至少需要一个资料类别 / Recipe requires at least one item")
    kinds = set()
    for item in items:
        if not isinstance(item, dict):
            raise DeliveryError("资料类别必须是对象 / Item must be an object")
        kind = safe_name(item.get("kind"))
        if kind in kinds:
            raise DeliveryError("资料类别不能重复 / Duplicate item kind")
        kinds.add(kind)
        low, high = item.get("min_count", 1), item.get("max_count", 1)
        if type(low) is not int or type(high) is not int or not 0 <= low <= high <= 10000:
            raise DeliveryError("资料数量范围无效 / Invalid item count range")
        extensions = item.get("extensions")
        if not isinstance(extensions, list) or not extensions or any(
            not isinstance(x, str) or not re.fullmatch(r"\.[A-Za-z0-9]+", x) for x in extensions
        ):
            raise DeliveryError("请列出允许的文件扩展名 / List allowed file extensions")
    return pattern


def plan(source, recipe):
    pattern = validate_recipe(recipe)
    root = Path(source)
    if root.is_symlink() or not root.is_dir():
        raise DeliveryError("请选择真实的资料文件夹 / Choose an existing source directory")
    root = root.resolve()
    rules = {item["kind"]: item for item in recipe["items"]}
    buckets, ignored = {}, []
    for parent, folders, files in os.walk(root, followlinks=False):
        for folder in list(folders):
            if (Path(parent) / folder).is_symlink():
                folders.remove(folder)
                ignored.append({"path": (Path(parent) / folder).relative_to(root).as_posix(), "reason": "symlink"})
        for filename in sorted(files):
            path = Path(parent) / filename
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                ignored.append({"path": relative, "reason": "symlink"})
                continue
            match = pattern.fullmatch(filename)
            if not match:
                ignored.append({"path": relative, "reason": "unmatched"})
                continue
            groups = match.groupdict()
            project, kind = groups["project"], groups["kind"]
            if project not in recipe["projects"] or kind not in rules:
                ignored.append({"path": relative, "reason": "outside_recipe"})
                continue
            if path.suffix.lower() not in [x.lower() for x in rules[kind]["extensions"]]:
                ignored.append({"path": relative, "reason": "extension"})
                continue
            if not groups["version"].isascii() or not groups["version"].isdecimal() or int(groups["version"]) > 9007199254740991:
                raise DeliveryError("版本必须是非负整数 / Version must be a nonnegative integer: " + relative)
            record = {"path": relative, "sha256": digest(path), "bytes": path.stat().st_size,
                      "version": int(groups["version"]), "kind": kind, "slot": groups.get("slot") or "main"}
            buckets.setdefault((project, kind, record["slot"]), []).append(record)
    projects = []
    for project in recipe["projects"]:
        selected, issues, discarded = [], [], []
        for (owner, kind, slot), candidates in sorted(buckets.items()):
            if owner != project:
                continue
            latest = max(x["version"] for x in candidates)
            current = sorted([x for x in candidates if x["version"] == latest], key=lambda x: x["path"])
            discarded.extend(x for x in candidates if x["version"] < latest)
            if len({x["sha256"] for x in current}) > 1:
                issues.append({"code": "conflict", "kind": kind, "slot": slot, "paths": [x["path"] for x in current]})
                continue
            selected.append(current[0])
            discarded.extend(current[1:])
        for kind, rule in rules.items():
            count = sum(x["kind"] == kind for x in selected)
            if count < rule.get("min_count", 1):
                issues.append({"code": "missing", "kind": kind, "have": count, "need": rule.get("min_count", 1)})
            if count > rule.get("max_count", 1):
                issues.append({"code": "excess", "kind": kind, "have": count, "limit": rule.get("max_count", 1)})
        # The archive never flattens files that would have the same destination.
        destinations = [x["kind"] + "/" + Path(x["path"]).name for x in selected]
        if len({x.casefold() for x in destinations}) != len(destinations):
            issues.append({"code": "destination_collision", "kind": ""})
        projects.append({"id": project, "ready": not issues, "files": sorted(selected, key=lambda x: x["path"]),
                         "issues": issues, "discarded": sorted(discarded, key=lambda x: x["path"])})
    report = {"schema": 1, "recipe": recipe, "projects": projects,
              "ignored": sorted(ignored, key=lambda x: x["path"])}
    report["fingerprint"] = hashlib.sha256(canonical(report).encode("utf-8")).hexdigest()
    return report


def inventory(project):
    return {"schema": 1, "project": project["id"], "files": [
        {"member": x["kind"] + "/" + Path(x["path"]).name, "sha256": x["sha256"], "bytes": x["bytes"],
         "source": x["path"], "version": x["version"]} for x in project["files"]]}


def zip_info(name):
    result = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
    result.compress_type = zipfile.ZIP_DEFLATED
    result.create_system = 3
    result.external_attr = 0o100644 << 16
    return result


def verify_archive(path, expected=None):
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)) or "inventory.json" not in members:
            raise DeliveryError("交付包清单缺失或文件重名 / Missing inventory or duplicate archive member")
        for name in members:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise DeliveryError("交付包路径无效 / Invalid archive path")
        manifest = json.loads(archive.read("inventory.json"))
        if expected is not None and manifest != expected:
            raise DeliveryError("交付包与本次清单不同 / Archive differs from expected inventory")
        if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), list):
            raise DeliveryError("交付包清单无效 / Invalid inventory")
        required = [x["member"] for x in manifest["files"]]
        if len(required) != len(set(required)) or set(members) != {"inventory.json", *required}:
            raise DeliveryError("交付包文件数量不一致 / Archive members differ from inventory")
        for record in manifest["files"]:
            hasher, length = hashlib.sha256(), 0
            with archive.open(record["member"]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
                    length += len(block)
            if length != record["bytes"] or hasher.hexdigest() != record["sha256"]:
                raise DeliveryError("交付包文件内容不一致 / Archive content mismatch: " + record["member"])
    return {"passed": True, "project": manifest["project"], "files": len(required)}


def summary(report, lang="zh"):
    ready = sum(x["ready"] for x in report["projects"])
    if lang == "en":
        lines = [f"Projects: {len(report['projects'])}; ready: {ready}; blocked: {len(report['projects'])-ready}"]
    else:
        lines = [f"项目：{len(report['projects'])}；资料齐全：{ready}；需要补齐或处理：{len(report['projects'])-ready}"]
    for project in report["projects"]:
        lines.append(project["id"] + (": ready" if lang == "en" else "：资料齐全") if project["ready"] else
                     project["id"] + (": blocked" if lang == "en" else "：未生成交付包"))
        for issue in project["issues"]:
            code = issue["code"]
            if code == "missing":
                text = f"{issue['kind']}: {issue['have']}/{issue['need']}" + (" required" if lang == "en" else "，请补齐")
            elif code == "conflict":
                text = issue["kind"] + (": same version has different contents" if lang == "en" else "：同版本存在不同内容，请保留正确文件")
            elif code == "excess":
                text = issue["kind"] + (": too many files" if lang == "en" else "：文件数量超过要求，请调整清单或资料")
            else:
                text = "Resolve colliding names" if lang == "en" else "请处理重复的输出文件名"
            lines.append("  " + text)
    return "\n".join(lines) + "\n"


def build(source, recipe, output, planned=None):
    root = Path(source).resolve()
    target = Path(output)
    if target.is_symlink():
        raise DeliveryError("输出不能是目录链接 / Output cannot be a symlink")
    target = target.resolve()
    if target == root or target.is_relative_to(root) or root.is_relative_to(target):
        raise DeliveryError("输入和输出需要使用独立文件夹 / Input and output must use separate directories")
    current = plan(root, recipe)
    if planned is not None and current != planned:
        raise DeliveryError("资料已变化，请重新检查 / Files changed; review a new plan")
    target.mkdir(parents=True, exist_ok=True)
    run = target / ("run-" + current["fingerprint"][:16])
    lock = target / (run.name + ".lock")
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DeliveryError("相同交付正在运行，请等它完成 / The same delivery is already running") from exc
    os.close(handle)
    try:
        if run.exists():
            if run.is_symlink() or not run.is_dir():
                raise DeliveryError("已有交付目录无效 / Invalid existing delivery directory")
            result = json.loads((run / "Report.json").read_text(encoding="utf-8"))
            if result.get("fingerprint") != current["fingerprint"]:
                raise DeliveryError("已有交付记录不一致 / Existing delivery differs")
            if result.get("projects") != current["projects"] or result.get("recipe") != recipe:
                raise DeliveryError("已有交付记录已变化 / Existing report was changed")
            for lang in ["zh", "en"]:
                if (run / f"Summary.{lang}.txt").read_text(encoding="utf-8") != summary(current, lang):
                    raise DeliveryError("已有交付摘要已变化 / Existing summary was changed")
            for project in current["projects"]:
                if project["ready"]:
                    package = run / (project["id"] + ".zip")
                    if package.is_symlink():
                        raise DeliveryError("交付包不能是文件链接 / Package cannot be a symlink")
                    verify_archive(package, inventory(project))
            return {"report": current, "directory": str(run), "reused": True}
        with tempfile.TemporaryDirectory(prefix=".delivery-", dir=target) as temp:
            stage = Path(temp) / run.name
            stage.mkdir()
            for project in current["projects"]:
                if not project["ready"]:
                    continue
                expected = inventory(project)
                with zipfile.ZipFile(stage / (project["id"] + ".zip"), "w") as archive:
                    for record, item in zip(project["files"], expected["files"]):
                        original = root / record["path"]
                        if original.is_symlink() or not original.resolve().is_relative_to(root):
                            raise DeliveryError("原资料路径发生变化 / Source path changed")
                        with original.open("rb") as stream, archive.open(zip_info(item["member"]), "w") as dest:
                            for block in iter(lambda: stream.read(1024 * 1024), b""):
                                dest.write(block)
                    archive.writestr(zip_info("inventory.json"), canonical(expected).encode("utf-8"))
                verify_archive(stage / (project["id"] + ".zip"), expected)
            # Recheck all selections before any completed output becomes visible.
            if plan(root, recipe) != current:
                raise DeliveryError("运行期间资料已变化，请重新检查 / Source changed during packaging")
            (stage / "Report.json").write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
            for lang in ["zh", "en"]:
                (stage / f"Summary.{lang}.txt").write_text(summary(current, lang), encoding="utf-8")
            stage.rename(run)
        return {"report": current, "directory": str(run), "reused": False}
    finally:
        lock.unlink(missing_ok=True)
