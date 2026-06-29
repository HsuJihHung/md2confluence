# build/md2confluence.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect NiceGUI static files (templates, JS, CSS)
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all("nicegui")

# conda puts ffi-8.dll in Library/bin, not DLLs — PyInstaller misses it.
# _ctypes.pyd (in DLLs) depends on it at runtime, so bundle it explicitly.
_env = Path(sys.prefix)
_ffi_binaries = [(str(dll), '.') for dll in _env.glob("Library/bin/ffi*.dll")]

a = Analysis(
    ["../app.py"],
    pathex=[str(Path("..").resolve())],
    binaries=nicegui_binaries + _ffi_binaries,
    datas=nicegui_datas,
    hiddenimports=nicegui_hiddenimports + [
        "services.confluence_config",
        "services.file_tracker",
        "services.upload_service",
        "services.download_service",
        "ui.main_layout",
        "ui.config_page",
        "ui.download_dialog",
        # CLI entry points bundled as modules so _build_cmd fallback works
        "md2conf",
        "confluence_markdown_exporter",
    ],
    hookspath=[],
    runtime_hooks=[str(Path(SPECPATH) / "rthook_nullio.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="md2confluence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window on Windows
    icon=None,
)
