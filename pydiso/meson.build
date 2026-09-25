cython_file = custom_target(
    input: '_mkl_solver.in.pyx',
    output: '_mkl_solver.pyx',
    command: [py,
  '-c',
'''
import sys
from pathlib import Path
from Cython.Tempita import sub

template = Path(sys.argv[1]).read_text("utf8")
output = sub(template)
Path(sys.argv[2]).write_text(output, "utf8")
''', '@INPUT@', '@OUTPUT@']
)

# NumPy include directory
np_dep = dependency('numpy')
numpy_nodepr_api = ['-DNPY_NO_DEPRECATED_API=NPY_1_9_API_VERSION']

# MKL's single dynamic library (mkl_rt), through pkg-config. It picks its
# threading layer at runtime (MKL_THREADING_LAYER), so there's no threading
# choice to make here. mkl_pkgconfig.py also searches PyPI mkl-devel's .pc
# files, which pkg-config doesn't find on its own.
mkl_pkgconfig = meson.project_source_root() / 'tools' / 'mkl_pkgconfig.py'
mkl_deps = []
pkg_config = find_program('pkg-config', 'pkgconf', required: false)
if pkg_config.found()
    mkl_version = run_command(py, mkl_pkgconfig, pkg_config, '--modversion', check: false)
    if mkl_version.returncode() == 0 and mkl_version.stdout().strip().version_compare('>=2023.0')
        mkl_cflags = run_command(py, mkl_pkgconfig, pkg_config, '--cflags', check: true)
        mkl_libs = run_command(py, mkl_pkgconfig, pkg_config, '--libs', check: true)
        mkl_deps += declare_dependency(
            compile_args: mkl_cflags.stdout().strip().split('\n'),
            link_args: mkl_libs.stdout().strip().split('\n'),
        )
    endif
endif
if mkl_deps.length() == 0 and not get_option('dist_ignore_mkl_dep')
    error('MKL (>=2023.0) not found through pkg-config: install mkl-devel and put its mkl-sdl.pc on PKG_CONFIG_PATH.')
endif

cython_args = []
if cy.version().version_compare('>=3.1.0')
  cython_args += ['-Xfreethreading_compatible=True']
endif

c_undefined_ok = ['-Wno-maybe-uninitialized']
cython_c_args = [numpy_nodepr_api, '-DCYTHON_CCOMPLEX=0']

module_path = 'pydiso'

# PyPI's `mkl` wheel puts its libraries under `<prefix>/lib`, off the
# loader's default search path from site-packages. rpath both possible
# depths (venv vs. plain prefix) so it's found without
# LD_LIBRARY_PATH/DYLD_LIBRARY_PATH, mirroring mkl-service. No-op for
# conda-forge builds, where those dirs don't exist.
rpath_link_args = []
if host_machine.system() != 'windows'
    if host_machine.system() == 'darwin'
        origin = '@loader_path'
    else
        origin = '$ORIGIN'
    endif

    rpath_link_args = [
        '-Wl,-rpath,' + origin / '../..',
        '-Wl,-rpath,' + origin / '../../..',
    ]
endif

# Limited to the 3.12 API subset so this produces one abi3 wheel instead
# of one per Python version (see pyproject.toml's `limited-api` setting).
# Meson gates this on `python.allow_limited_api`, so
# `-Dpython.allow_limited_api=false` cleanly disables it (needed for
# free-threaded builds, which Cython can't yet target the stable ABI for).
py.extension_module(
    '_mkl_solver',
    cython_file,
    cython_args: cython_args,
    c_args: cython_c_args,
    link_args: rpath_link_args,
    install: true,
    subdir: module_path,
    dependencies : [py_dep, np_dep] + mkl_deps,
    limited_api: '3.12',
)

python_sources = [
  '__init__.py', 'mkl_solver.py', '_init_helper.py'
]

py.install_sources(
  python_sources,
  subdir: module_path
)