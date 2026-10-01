# PANDAO Delivery Pack

[中文](README.md) · [Use in your browser](https://tianchaodaxing-beep.github.io/pandao-delivery-pack/?lang=en) · [Download the local tool](https://github.com/tianchaodaxing-beep/pandao-delivery-pack/releases/tag/v0.1.0)

A folder contains designs, guides and images for dozens of projects, mixed with old versions and duplicate copies. Give this tool a delivery recipe. It selects the latest version for each item slot, lists missing files and conflicting versions, and builds a separate ZIP for every complete project.

Use your own recipes for design handovers, engineering records, manufacturing documentation, training materials or client attachments.

## Browser use

1. Open the page and choose **Try sample files**. The three fictional projects show a complete delivery, a missing guide and a same-version conflict.
2. Choose **Download packages** to get an actual ZIP containing the complete project's files, Chinese and English summaries, and the project report.
3. Choose your own folder, edit the recipe's project IDs, categories, extensions and quantities, then check and download.

Files stay in the current browser and are never uploaded. Use up to 250 MB in the browser; use the local tool for larger folders. Neither tool moves or deletes original files. The tool checks completeness against your recipe. The delivery owner must still confirm that each file's contents are correct.

## Local use

Requires Python 3.11 or later. There are no third-party runtime dependencies.

Download and extract the local tool, then run these commands in its folder:

```sh
python -m pip install .
pandao-delivery plan --source ./files --recipe ./recipe.json
pandao-delivery build --source ./files --recipe ./recipe.json --output ./delivery
pandao-delivery --lang en build --source ./files --recipe ./recipe.json --output ./delivery
pandao-delivery verify ./delivery/run-ID/P001.zip
```

On Windows, double-click `打开交付包工具.cmd` to open the local browser tool. Run `python 运行示例.py` to create clearly labelled sample files and build sample delivery packages.

Use separate input and output folders. Repeating the same recipe and files verifies and reuses the existing delivery. Changed inputs create a new delivery directory while keeping the old one. Exit code `0` means all projects are complete, `2` means complete projects were processed while others need attention, and `1` means the run failed.

## Delivery recipe

File names must identify the project, category, slot and version, for example:

```text
P001_design_main_v2.svg
P001_guide_main_v1.txt
P001_image_front_v1.svg
P001_image_back_v1.svg
```

Download the full sample recipe from the browser tool. This smaller example covers one project. Adapt its matching pattern to your naming convention:

```json
{
  "schema": 1,
  "filename_pattern": "(?P<project>[^_]+)_(?P<kind>[^_]+)_(?P<slot>[^_]+)_v(?P<version>\\d+)\\.[^.]+",
  "projects": ["P001"],
  "items": [
    {"kind": "design", "extensions": [".svg", ".pdf"], "min_count": 1, "max_count": 1},
    {"kind": "guide", "extensions": [".txt", ".pdf"], "min_count": 1, "max_count": 1},
    {"kind": "image", "extensions": [".svg", ".png", ".jpg"], "min_count": 2, "max_count": 2}
  ]
}
```

`projects` lists every expected project, even those with no files at all. `kind` identifies a category, and `slot` distinguishes separate items within that category, such as front and back images. `version` is a nonnegative integer: `v10` is newer than `v2`. The latest version is selected for each slot. Identical copies at the same version are merged; different contents at the same version become a conflict. Use `min_count: 0` for optional items.

Unmatched names, extensions and project IDs remain in the report. Projects with missing files, conflicts or excess quantities receive no package, while other complete projects are processed. If your file names lack version information, first standardize them or adapt the pattern.

Each project ZIP contains the original files and `inventory.json`. The overall result includes `Report.json`, `Summary.zh.txt` and `Summary.en.txt`. The local `verify` command checks archive contents against their inventory.

## License

MIT. Commercial use is allowed; preserve the license when distributing.
