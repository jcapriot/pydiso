"""Query pkg-config for MKL's single dynamic library, for pydiso/meson.build
(a build-time helper: it isn't installed with the package).

Usage: mkl_pkgconfig.py <pkg-config> --modversion|--cflags|--libs

PyPI's mkl-devel installs its .pc files where pkg-config doesn't look, and
meson's own pkg_config_path option can't be relied on to add them: an
environment PKG_CONFIG_PATH (the manylinux images set one) outranks a
project default. So this adds mkl-devel's directory, found through its
installed metadata, to whatever PKG_CONFIG_PATH already exists. That also
works under pip build isolation, where mkl-devel is installed into an
overlay unrelated to sysconfig's paths.

Prints the version, or one flag per line (parsed with shlex, so paths with
spaces survive). Exits non-zero if pkg-config can't find MKL.
"""

import importlib.metadata as md
import os
import shlex
import subprocess
import sys


def mkl_devel_pc_dir():
    try:
        dist = md.distribution("mkl-devel")
    except md.PackageNotFoundError:
        return None
    for f in dist.files or ():
        if os.path.basename(str(f)) == "mkl-sdl.pc":
            return os.path.dirname(os.path.normpath(str(dist.locate_file(f))))
    return None


def main():
    pkg_config, query = sys.argv[1:]

    env = dict(os.environ)
    pc_dir = mkl_devel_pc_dir()
    if pc_dir:
        env["PKG_CONFIG_PATH"] = os.pathsep.join(filter(None, [pc_dir, env.get("PKG_CONFIG_PATH")]))

    proc = subprocess.run([pkg_config, query, "mkl-sdl"], env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)

    if query == "--modversion":
        print(proc.stdout.strip())
    else:
        print("\n".join(shlex.split(proc.stdout)))


if __name__ == "__main__":
    main()
