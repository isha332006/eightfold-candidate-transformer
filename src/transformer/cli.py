#!/usr/bin/env python3
"""CLI for the Multi-Source Candidate Data Transformer.

Usage:
    python -m transformer.cli --sources file1.csv file2.json resume.docx notes.txt --out output.json
    python -m transformer.cli --sources file1.csv resume.pdf --config configs/example_config.json --out custom.json
"""
import argparse
import json
import sys

from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--sources", nargs="+", required=True,
                         help="Paths/URLs to source files (CSV, ATS JSON, resume PDF/DOCX, "
                              "recruiter notes .txt, GitHub profile URL, LinkedIn export JSON/URL)")
    parser.add_argument("--config", help="Path to a runtime projection config JSON file")
    parser.add_argument("--out", default="-", help="Output path for JSON ('-' for stdout)")
    parser.add_argument("--strict", action="store_true",
                         help="Fail the run on projection errors instead of degrading")
    parser.add_argument("--pretty", action="store_true", default=True)
    args = parser.parse_args()

    config = None
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

    result = run_pipeline(args.sources, config=config, strict=args.strict)

    output = {"profiles": result["profiles"]}
    text = json.dumps(output, indent=2, ensure_ascii=False)

    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {len(result['profiles'])} profile(s) to {args.out}", file=sys.stderr)

    for w in result["warnings"]:
        print(f"[warn] {w}", file=sys.stderr)
    for e in result["errors"]:
        print(f"[error] {e}", file=sys.stderr)

    if result["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
