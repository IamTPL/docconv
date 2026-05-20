# docconv/cli.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docconv.config import load_config, init_config, show_config
from docconv.converters.base import UnsupportedFormatError
from docconv.router import route
from docconv.utils.postprocess import clean_markdown

_SUPPORTED = {".pdf", ".xlsx", ".xls", ".xlsm", ".csv", ".tsv", ".docx", ".doc", ".odt"}


def _resolve_output(input_path: Path, output_arg: str, config) -> Path:
    out = Path(output_arg)
    if output_arg.endswith("/") or out.is_dir():
        out.mkdir(parents=True, exist_ok=True)
        return out / (input_path.stem + ".md")
    return out


def _convert_file(input_path: Path, output_arg: str, config, force_scan: bool = False) -> bool:
    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}", file=sys.stderr)
        return False
    output_path = _resolve_output(input_path, output_arg, config)
    try:
        converter = route(input_path, force_scan=force_scan)
        engine = type(converter).__name__.replace("Converter", "")
        print(f"[•] {input_path.name}  →  engine: {engine}")
        markdown = converter.convert(input_path, config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(clean_markdown(markdown), encoding="utf-8")
        print(f"[✓] {output_path}")
        return True
    except UnsupportedFormatError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] {input_path.name}: {e}", file=sys.stderr)
        if config.verbose:
            import traceback
            traceback.print_exc()
        return False


def _convert_dir(input_dir: Path, output_arg: str, config, force_scan: bool = False) -> None:
    files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _SUPPORTED
    )
    if not files:
        print(f"[!] No supported files in {input_dir}")
        return
    out_dir = Path(output_arg)
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_output = str(out_dir) + "/"
    ok = sum(_convert_file(f, batch_output, config, force_scan=force_scan) for f in files)
    print(f"\nDone: {ok}/{len(files)} converted.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docconv",
        description="Convert documents (PDF/Excel/Word) to Markdown",
    )
    parser.add_argument("input", nargs="?", help="Input file or directory")
    parser.add_argument("-o", "--output", metavar="PATH", help="Output file (.md) or directory (required when converting)")
    parser.add_argument("--sheets", metavar="NAMES", help="Excel sheets, comma-separated")
    parser.add_argument("--header-rows", type=int, metavar="N", help="Number of header rows in Excel")
    parser.add_argument("--force-scan", action="store_true", dest="force_scan",
                        help="Force Gemini API (PDFScan engine) even for digital PDFs")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    parser.add_argument("--init-config", action="store_true", dest="init_config", help="Create ~/.docconv.yaml")
    parser.add_argument("--show-config", action="store_true", dest="show_config", help="Print active configuration")

    args = parser.parse_args()

    if args.init_config:
        init_config()
        return

    if args.show_config:
        show_config()
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    if not args.output:
        print("[ERROR] Output path is required. Use -o <file.md> or -o <directory/>", file=sys.stderr)
        sys.exit(1)

    overrides: dict = {}
    if args.verbose:
        overrides["verbose"] = True
    if args.sheets:
        overrides.setdefault("spreadsheet", {})["sheets"] = args.sheets.split(",")
    if args.header_rows is not None:
        overrides.setdefault("spreadsheet", {})["header_rows"] = args.header_rows

    config = load_config(overrides)
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"[ERROR] Not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.is_dir():
        _convert_dir(input_path, args.output, config, force_scan=args.force_scan)
    else:
        if not _convert_file(input_path, args.output, config, force_scan=args.force_scan):
            sys.exit(1)


if __name__ == "__main__":
    main()
