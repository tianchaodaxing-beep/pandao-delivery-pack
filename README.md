# PANDAO 交付包自动组装

[English](README.en.md) · [在线使用](https://tianchaodaxing-beep.github.io/pandao-delivery-pack/?lang=zh) · [下载本机版](https://github.com/tianchaodaxing-beep/pandao-delivery-pack/releases/tag/v0.1.0)

一个文件夹里有几十个项目的设计文件、说明、配图，还有旧版本和重复副本。给出交付清单，这个工具会自动挑选每个资料位置的最新版本、检查缺件和同版本冲突，再为资料齐全的项目生成 ZIP 交付包。

适用于设计交付、工程资料、制造配套文件、培训和客户服务附件。每种工作使用自己的交付清单。

## 网页使用

1. 打开在线页面，点击“用示例试一次”。示例是三个虚构项目：一个齐全，一个缺说明，一个有同版本冲突。
2. 点击“下载交付包”，可得到一个实际 ZIP，内有齐全项目的独立资料包、中英文摘要和检查结果。
3. 换成自己的资料：选择文件夹，修改交付清单中的项目编号、类别、扩展名和数量，再检查、下载。

资料只在当前浏览器内处理，不上传。网页适合不超过 250 MB 的资料；更大的文件夹使用下面的本机版。网页和本机版都不会移动或删除原资料。工具检查资料是否按清单备齐；文件本身是否正确仍需由交付方确认。

## 本机使用

需要 Python 3.11 或以上。没有第三方运行依赖。

下载并解压本机版后，在工具文件夹执行：

```powershell
py -3.11 -m pip install .
pandao-delivery plan --source "./资料" --recipe "./交付清单.json"
pandao-delivery build --source "./资料" --recipe "./交付清单.json" --output "./交付结果"
pandao-delivery --lang en build --source "./资料" --recipe "./交付清单.json" --output "./交付结果"
pandao-delivery verify "./交付结果/run-编号/P001.zip"
```

也可以双击“打开交付包工具.cmd”使用本机网页。运行 `py -3.11 运行示例.py` 会创建明确标记的模拟资料并生成交付结果。

输入与输出须使用独立文件夹。再次运行相同资料与清单时，核对后复用已有交付；资料变化时生成新的交付目录，原交付保留。退出码 `0` 表示全部项目齐全，`2` 表示齐全项目已处理但有项目需要补件或处理冲突，`1` 表示运行失败。

## 交付清单

文件名需要能识别项目、资料类别、位置和版本，例如：

```text
P001_design_main_v2.svg
P001_guide_main_v1.txt
P001_image_front_v1.svg
P001_image_back_v1.svg
```

网页提供可下载的完整清单。下面是单项目简例；可按自己的命名方式修改匹配规则：

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

`projects` 列出本次必须交付的项目，包括一个文件都没有的项目。`kind` 是资料类别，`slot` 区分同类别里的不同资料，例如正面和背面。`version` 使用非负整数：`v10` 比 `v2` 新。每个位置只选最新版本；同版本、同内容的副本合并，同版本、不同内容的文件列为冲突。`min_count: 0` 可表示选交资料。

不符合命名规则、扩展名或项目清单的文件会列在检查结果里。一个项目缺件、冲突或超出数量要求时，不生成该项目交付包，其余齐全项目继续处理。文件名不含版本信息时，请先统一命名，或调整清单的匹配规则。

每个项目 ZIP 内有原资料和 `inventory.json`；总结果中有 `Report.json`、`Summary.zh.txt`、`Summary.en.txt`。本机 `verify` 命令可以核对包内文件是否与清单一致。

## 许可证

MIT。可以商用；分发时保留许可证。
