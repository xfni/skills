"""Fail closed until Cursor proves disabled tools AND implicit indexing.

The workspace bridge provides no such guarantee. No SDK, credential, input file
or network is accessed for a capability check or review request.
"""
import argparse
import json
import sys


def emit_error(code, message):
    print(message, file=sys.stderr)
    print("FLOW_REVIEW_ERROR_BEGIN", file=sys.stderr)
    print(json.dumps({"schema_version": 1, "code": code}), file=sys.stderr)
    print("FLOW_REVIEW_ERROR_END", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Cursor byte-review adapter")
    parser.add_argument("request_file", nargs="?")
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--expected-request-digest")
    parser.add_argument("--check-capabilities", action="store_true")
    parser.add_argument("--model", default="grok-4.6")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout-seconds", type=int, default=960)
    parser.parse_args()
    emit_error("BACKEND_UNAVAILABLE",
               "INCOMPLETE: Cursor SDK cannot prove disabled tools and implicit indexing.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
