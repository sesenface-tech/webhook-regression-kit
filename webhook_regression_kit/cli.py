import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__
from .generator import SCENARIOS, generate


def read_json(path):
    with Path(path).open("rb") as handle:
        content = handle.read(1048577)
    if len(content) > 1048576:
        raise ValueError("Input exceeds 1 MiB")
    return json.loads(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a local unittest from webhook JSON and explicit expected receiver state")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--output", required=True, help="New .py file; existing files are never overwritten")
    parser.add_argument("--scenario", choices=SCENARIOS, default="duplicate")
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--wait", type=float, default=0)
    parser.add_argument("--redact-values-file", help="Local JSON array of extra strings to replace; never put secrets in CLI arguments")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if output.suffix != ".py":
            raise ValueError("Output must be .py")
        values = read_json(args.redact_values_file) if args.redact_values_file else []
        if not isinstance(values, list):
            raise ValueError("Redaction values must be an array")
        source, summary = generate(read_json(args.events), read_json(args.expected), args.scenario, args.delay, args.wait, values)
        # O_EXCL prevents overwriting inputs, existing files, or symlink destinations.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(source)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, RecursionError):
        print("Generation failed: check JSON, input limits, timing, and that output is a new .py file.", file=sys.stderr)
        return 2
