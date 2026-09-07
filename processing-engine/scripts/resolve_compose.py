#!/usr/bin/env python3
"""Resolve ${VAR} and ${VAR:-default} patterns in a compose file.

Reads env vars directly from the process environment and writes the resolved
file. Dollar signs ($) in resolved values are escaped as $$ so Docker Compose
treats them as literal characters instead of trying to interpolate them.

Usage:
    python3 resolve_compose.py <input.yml> <output.yml>
"""

import os
import re
import sys


def replace_var(m: re.Match) -> str:
    var_name = m.group(1)
    default = m.group(2) or ""
    val = os.environ.get(var_name, default)
    # Escape literal $ as $$ for Docker Compose
    return val.replace("$", "$$")


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.yml> <output.yml>", file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    with open(input_path) as f:
        content = f.read()

    # Resolve ${VAR} and ${VAR:-default} patterns
    content = re.sub(
        r"\$\{([A-Za-z_]\w*)(?::-([^}]*))?\}", replace_var, content
    )

    with open(output_path, "w") as f:
        f.write(content)

    # Print sanitized version for CI logs
    print("=== Resolved compose file (sanitized) ===")
    for line in content.splitlines():
        stripped = line.strip()
        if any(k in stripped for k in ["PASSWORD", "KEY", "SECRET"]):
            if "=" in stripped:
                key, _, val = stripped.partition("=")
                if len(val) > 4:
                    print(f"  {key}={val[:2]}***{val[-2:]}")
                else:
                    print(f"  {key}=***")
            continue
        # Don't print non-sensitive lines to keep logs clean


if __name__ == "__main__":
    main()
