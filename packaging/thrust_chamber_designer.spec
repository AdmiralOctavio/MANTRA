# PyInstaller spec of the desktop app: pyinstaller packaging/thrust_chamber_designer.spec
# Builds a folder dist/ThrustChamberDesigner with the executable. Run it from the root of the repository with the package installed.
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# gmsh looks for its library next to gmsh.py, which is the top folder of the app
gmsh_libs = []
for pattern in ("libgmsh.so*", "libgmsh*.dylib", "gmsh-*.dll"):
    for root in (sys.prefix, os.path.join(sys.prefix, "lib"), os.path.join(sys.prefix, "Lib"), os.path.join(sys.prefix, "bin")):
        gmsh_libs += [(path, ".") for path in glob.glob(os.path.join(root, pattern))]
if not gmsh_libs:
    raise SystemExit("gmsh library not found under " + sys.prefix + ", install the gmsh package from pip")

datas = (collect_data_files("cea") + collect_data_files("plotly") + collect_data_files("CoolProp")
         + collect_data_files("thrust_chamber_designer"))
binaries = gmsh_libs + collect_dynamic_libs("cea") + collect_dynamic_libs("CoolProp")
hiddenimports = (collect_submodules("fipy.solvers") + collect_submodules("fipy.meshes") + collect_submodules("thrust_chamber_designer")
                 + ["gmsh", "matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_agg"])

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # QtWebEngine (Chromium) would add about 400 MB for the embedded 3D view, which opens in the web browser without it
    excludes=["tkinter", "PyQt5", "PyQt6", "IPython", "pytest", "streamlit", "rocketcea",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
# icon of the exe in the Explorer and on the desktop, the same file the window uses
icon = os.path.join(SPECPATH, os.pardir, "src", "thrust_chamber_designer", "gui", "icons", "app.ico")
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ThrustChamberDesigner",
    console=False,
    icon=icon if os.path.exists(icon) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ThrustChamberDesigner")
