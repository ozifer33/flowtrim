#!/usr/bin/env python3
from __future__ import annotations

import argparse

from flowtrim.classifier import classify_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a FlowTrim task into lanes.")
    parser.add_argument("text", help="Task or artifact description to classify.")
    args = parser.parse_args()
    for lane in classify_text(args.text):
        print(lane.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
