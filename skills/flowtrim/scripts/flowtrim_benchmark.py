#!/usr/bin/env python3
from __future__ import annotations

import argparse

from flowtrim.metrics import estimate_tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate tokens for benchmark fixture text.")
    parser.add_argument("text", help="Text to estimate.")
    args = parser.parse_args()
    print(estimate_tokens(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
