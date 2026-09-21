"""Replace Intel's OpenMP runtime in the build environment with LLVM's.

MKL's `mkl_intel_thread` layer only needs an OpenMP runtime exporting the
`__kmpc_*` interface, which LLVM's libomp provides (conda-forge's package
even ships it under Intel's names: libiomp5md.{dll,lib} / libiomp5.so).
Installing it over the Intel one in the build prefix, where MKLConfig.cmake
looks for it, makes the extension link - and the wheel repair step bundle -
LLVM OpenMP (Apache-2.0 WITH LLVM-exception) instead of Intel's
libiomp5 (Intel EULA). Run from before-build; see pyproject.toml.
"""

import hashlib
import io
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import zstandard

VERSION = "23.1.1"
PACKAGES = {
    "win32": (
        "https://conda.anaconda.org/conda-forge/win-64/llvm-openmp-23.1.1-h49e36cd_0.conda",
        "49b0967e84eae82cc2acaf4400629c7b9c08a491b9c8d3343f3f5f2feee7138d",
        ("Library/bin/libiomp5md.dll", "Library/lib/libiomp5md.lib"),
    ),
    "linux": (
        "https://conda.anaconda.org/conda-forge/linux-64/llvm-openmp-23.1.1-h7148c6a_0.conda",
        "4d6dab4691baec13109bc251506a74da448340b6a5de92de30563871105f8e7c",
        ("lib/libomp.so", "lib/libiomp5.so"),
    ),
}
LICENSE_MEMBER = "info/licenses/openmp/LICENSE.TXT"


def read_inner_tar(conda_zip: zipfile.ZipFile, prefix: str) -> tarfile.TarFile:
    (name,) = [n for n in conda_zip.namelist() if n.startswith(prefix) and n.endswith(".tar.zst")]
    raw = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(conda_zip.read(name))).read()
    return tarfile.open(fileobj=io.BytesIO(raw))


def main() -> None:
    url, sha256, wanted = PACKAGES["win32" if sys.platform == "win32" else "linux"]
    data = urllib.request.urlopen(url).read()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"sha256 mismatch for {url}")
    conda_zip = zipfile.ZipFile(io.BytesIO(data))

    # Nothing may link or bundle Intel's runtime: remove it before installing ours.
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "intel-openmp"], check=True)

    prefix = Path(sys.prefix)
    pkg = read_inner_tar(conda_zip, "pkg-")
    for member in pkg.getmembers():
        if member.name.startswith(("lib/", "Library/")) and member.name.rsplit("/", 1)[-1].startswith(("libomp", "libiomp5")):
            if member.issym():  # keep libiomp5.so -> libomp.so relative
                (prefix / member.name).parent.mkdir(parents=True, exist_ok=True)
                (prefix / member.name).unlink(missing_ok=True)
            pkg.extract(member, prefix, filter="tar")
    for rel in wanted:
        if not (prefix / rel).exists():
            raise SystemExit(f"{rel} not found in {url}")

    license_dir = prefix / "share" / "doc" / "llvm-openmp"
    license_dir.mkdir(parents=True, exist_ok=True)
    info = read_inner_tar(conda_zip, "info-")
    (license_dir / "LICENSE.TXT").write_bytes(info.extractfile(LICENSE_MEMBER).read())
    print(f"installed LLVM OpenMP {VERSION} into {prefix}")


if __name__ == "__main__":
    main()
