# SPDX-License-Identifier: Apache-2.0
"""Entry point of the frozen app on every platform (PyInstaller runs this as ``__main__``).

Sets up the bundled STIR, then hands over to ``pet_projection_data_visualization.cli:main``.

Self-test (used by build_app.py and CI)::

    PETPDV_SELF_TEST=1 [PETPDV_SELF_TEST_LOG=out.txt] <frozen executable> (FILE | --demo) [--out PNG]

runs the bundled ``scripts/ci_smoke.py`` instead of opening the window, and reports where ``stir``
was imported from. The report goes to PETPDV_SELF_TEST_LOG when set, because a windowed Windows
executable has no stdout.
"""
from __future__ import annotations

import os
import sys


def _setup_bundle() -> None:
    base: str | None = getattr(sys, "_MEIPASS", None)    # set by PyInstaller in the frozen app
    if base is None:  # not frozen: running from a checkout
        return
    # STIR reads radionuclide/CT tables from a config dir compiled into the library. That path points
    # at the build machine (and conda-forge's relocation can leave it NUL-padded or naming another
    # version), so use the copy inside the bundle.
    # A user's own STIR_CONFIG_DIR is kept only if it really holds the tables; a stale or mistyped one
    # would otherwise make every .hs fail to load.
    config = os.path.join(base, "stir_config")
    user = os.environ.get("STIR_CONFIG_DIR", "")
    if os.path.isdir(config) and not os.path.isfile(os.path.join(user, "radionuclide_info.json")):
        os.environ["STIR_CONFIG_DIR"] = config
    # The bundle carries its own STIR; a STIR_PYTHON_PATH meant for another install would load a
    # second, ABI-incompatible copy of the SWIG module. (--stir-path still overrides on purpose.)
    os.environ.pop("STIR_PYTHON_PATH", None)
    # Very old macOS versions pass a process serial number when launched from Finder.
    sys.argv[1:] = [a for a in sys.argv[1:] if not a.startswith("-psn_")]


def _self_test(argv: list[str]) -> int:
    import runpy

    if not hasattr(sys, "_MEIPASS"):
        print("PETPDV_SELF_TEST only works in the frozen app; from a checkout run scripts/ci_smoke.py",
              file=sys.stderr)
        return 2

    log_path = os.environ.get("PETPDV_SELF_TEST_LOG")
    log = open(log_path, "w", encoding="utf-8") if log_path else None  # noqa: SIM115
    saved = sys.stdout, sys.stderr
    if log is not None:
        sys.stdout = sys.stderr = log
    try:
        bundle: str = getattr(sys, "_MEIPASS")     # not in the sys stub: PyInstaller adds it
        smoke = runpy.run_path(os.path.join(bundle, "ci_smoke.py"), run_name="ci_smoke")
        rc: int = smoke["main"](argv)
        import stir

        print(f"stir imported from {stir.__file__}")
        print(f"stir._stir loaded from {sys.modules['stir._stir'].__file__}")
        for lib in _loaded_native_libraries():
            print(f"native library {lib}")
        print(f"STIR_CONFIG_DIR={os.environ.get('STIR_CONFIG_DIR')}")
        print(f"exit status {rc}")
        return rc
    except BaseException:
        import traceback

        traceback.print_exc()  # into the log, which is all a windowed executable has
        return 1
    finally:
        if log is not None:
            log.flush()
            sys.stdout, sys.stderr = saved
            log.close()


def _loaded_native_libraries() -> list[str]:
    """Paths of the shared libraries loaded into this process."""
    if sys.platform.startswith("linux"):
        with open("/proc/self/maps", encoding="utf-8", errors="replace") as f:
            paths = {ln.split(None, 5)[5].strip() for ln in f if len(ln.split(None, 5)) == 6}
        return sorted(p for p in paths if p.startswith("/") and ".so" in os.path.basename(p))
    if sys.platform == "darwin":
        import ctypes

        dyld = ctypes.CDLL(None)
        dyld._dyld_image_count.restype = ctypes.c_uint32
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        return sorted(dyld._dyld_get_image_name(i).decode() for i in range(dyld._dyld_image_count()))
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        modules, needed = (wintypes.HMODULE * 4096)(), wintypes.DWORD()
        if not psapi.EnumProcessModules(kernel32.GetCurrentProcess(), modules, ctypes.sizeof(modules),
                                        ctypes.byref(needed)):
            return []
        buf, out = ctypes.create_unicode_buffer(32768), []
        for module in modules[: min(len(modules), needed.value // ctypes.sizeof(wintypes.HMODULE))]:
            if module and kernel32.GetModuleFileNameW(module, buf, len(buf)):
                out.append(buf.value)
        return sorted(out)
    return []


def main() -> int:
    _setup_bundle()
    if os.environ.get("PETPDV_SELF_TEST") == "1":
        return _self_test(sys.argv[1:])
    if sys.stdout is None:  # windowed Windows executable: give stray writes somewhere to go
        sys.stdout = sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    from pet_projection_data_visualization.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
