"""Adjust the metadata of the statically linked wheels built by cibuildwheel.

Run from `repair-wheel-command` (pyproject.toml) after auditwheel/delvewheel,
on every wheel in cibuildwheel's `{dest_dir}`, rewriting each in place:

- Strips the `mkl` requirement: MKL is linked in statically, but
  `dependencies` is static and shared with the source build, which needs it.
- Declares the licenses of the third-party binaries now inside the wheel (MKL
  itself, plus the bundled OpenMP runtime) alongside pydiso's own, and ships
  their license texts and third-party notices in the wheel's licenses/
  directory. Their terms require reproducing them with any redistribution.

Takes a directory rather than wheel paths so the same invocation works from
both sh and cmd.exe, which doesn't glob `*.whl`.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path


def license_files_of(dist_name: str) -> list[Path]:
    """License texts and third-party notices shipped by an installed Intel package."""
    dist = distribution(dist_name)
    found = [
        Path(dist.locate_file(f))
        for f in dist.files
        if (f.name.startswith("LICENSE") and f.parent.name.endswith(".dist-info"))
        or f.name.startswith("third-party-programs")
    ]
    if not any(p.name.startswith("LICENSE") for p in found):
        raise SystemExit(f"No LICENSE file found in installed package '{dist_name}'")
    return found


def finalize(
    wheel_path: Path, dependency: str, license_expression: str, license_dists: list[str], prefix_files: list[str]
) -> None:
    dest_dir = wheel_path.parent

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Shell out to `wheel`'s CLI: its Python API (wheel.cli) was made
        # private in 0.46 with no shim, but `python -m wheel` stays stable.
        subprocess.run(
            [sys.executable, "-m", "wheel", "unpack", str(wheel_path), "--dest", str(tmp)],
            check=True,
        )
        (unpacked_dir,) = tmp.iterdir()
        dist_info = next(unpacked_dir.glob("*.dist-info"))
        metadata_path = dist_info / "METADATA"
        text = metadata_path.read_text(encoding="utf-8")

        text, count = re.subn(rf"^Requires-Dist: {re.escape(dependency)}(\W.*)?$\n", "", text, flags=re.MULTILINE)
        if count == 0:
            raise SystemExit(f"'{dependency}' Requires-Dist not found in {wheel_path.name}; nothing to strip")

        text, count = re.subn(r"^License-Expression: .*$", f"License-Expression: {license_expression}", text, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f"Expected one License-Expression in {wheel_path.name} (needs PEP 639 metadata), found {count}")

        sources = [(d, src) for d in license_dists for src in license_files_of(d)]
        for f in prefix_files:  # e.g. share/doc/llvm-openmp/LICENSE.TXT, listed under its parent dir's name
            src = Path(sys.prefix) / f
            if not src.is_file():
                raise SystemExit(f"{src} not found")
            sources.append((src.parent.name, src))

        license_headers = []
        for group, src in sources:
            rel = Path(group) / src.name
            target = dist_info / "licenses" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            license_headers.append(f"License-File: {rel.as_posix()}\n")

        # License-File headers sit with the other headers, before the description body.
        head, sep, body = text.partition("\n\n")
        metadata_path.write_text(head + "\n" + "".join(license_headers).rstrip("\n") + sep + body, encoding="utf-8")

        # Repacking into the same directory overwrites wheel_path: the
        # filename is unchanged, and everything's already been extracted.
        result = subprocess.run(
            [sys.executable, "-m", "wheel", "pack", str(unpacked_dir), "--dest-dir", str(dest_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")

    match = re.search(r"^Repacking wheel as (?P<path>.+)\.\.\.", result.stdout, re.MULTILINE)
    if match is None or Path(match.group("path")) != wheel_path:
        raise SystemExit(f"Expected `wheel pack` to overwrite {wheel_path}, got: {result.stdout!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wheel_dir", type=Path, help="Directory of wheel(s) to process in place")
    parser.add_argument("--strip-dependency", default="mkl", help="Requirement to remove (default: mkl)")
    parser.add_argument("--license-expression", required=True, help="SPDX expression to declare for the wheel")
    parser.add_argument(
        "--license-from",
        nargs="+",
        default=[],
        metavar="DIST",
        help="Installed distributions whose license files and notices to ship in the wheel",
    )
    parser.add_argument(
        "--license-file-in-prefix",
        action="append",
        default=[],
        metavar="PATH",
        help="License file, relative to sys.prefix, to ship in the wheel (repeatable)",
    )
    args = parser.parse_args()

    for wheel_path in sorted(args.wheel_dir.glob("*.whl")):
        finalize(
            wheel_path, args.strip_dependency, args.license_expression, args.license_from, args.license_file_in_prefix
        )
        print(f"finalized {wheel_path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
