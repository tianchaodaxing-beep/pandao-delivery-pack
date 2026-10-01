"""Command line interface with Chinese and English summaries."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

from .core import DeliveryError, build, plan, summary, verify_archive


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    english = any(argv[i] == "--lang" and i + 1 < len(argv) and argv[i + 1] == "en" for i in range(len(argv)))
    text = lambda zh, en: en if english else zh
    parser = argparse.ArgumentParser(description=text("按交付清单自动组装资料包", "Assemble files into delivery packages"))
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help=text("结论语言", "Summary language"))
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ["plan", "build"]:
        command = sub.add_parser(name, help=text("检查资料", "Check files") if name == "plan" else text("生成交付包", "Build packages"))
        command.add_argument("--source", required=True)
        command.add_argument("--recipe", required=True)
        if name == "build":
            command.add_argument("--output", required=True)
    check = sub.add_parser("verify", help=text("核对交付包", "Verify a package"))
    check.add_argument("archive")
    args = parser.parse_args(argv)
    try:
        if args.action == "verify":
            result = verify_archive(args.archive)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8-sig"))
        if args.action == "build":
            result = build(args.source, recipe, args.output)
            report = result["report"]
            print(summary(report, args.lang), end="")
            print(("Output: " if args.lang == "en" else "已保存：") + result["directory"])
        else:
            report = plan(args.source, recipe)
            print(summary(report, args.lang), end="")
        return 0 if all(x["ready"] for x in report["projects"]) else 2
    except (DeliveryError, OSError, json.JSONDecodeError, zipfile.BadZipFile, KeyError) as exc:
        message = str(exc)
        print(message.split(" / ", 1)[1] if args.lang == "en" and " / " in message else message.split(" / ", 1)[0], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
