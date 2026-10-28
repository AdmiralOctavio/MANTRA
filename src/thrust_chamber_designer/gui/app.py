import multiprocessing
import os
import sys


def self_test(folder):
    """Nozzle and a coarse thermal simulation through the same separate process as the app uses, without a window. Checks a
    packaged app: ThrustChamberDesigner --self-test <folder>. Writes self_test.txt to the folder, exit code 0 if it worked."""
    import os
    import queue as queue_module

    from ..core.design import Design
    from .worker import thermal_job

    os.makedirs(folder, exist_ok=True)
    design = Design(name="self test")
    design.film.injector_fraction = 0.35
    design.thermal.step_size = 0.01
    design.thermal.cell_size_factor = 0.3
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=thermal_job, args=(design.to_dict(), folder, queue), daemon=True)
    process.start()
    lines, ok = [], False
    while True:
        try:
            message = queue.get(timeout=600)
        except queue_module.Empty:
            lines.append("No answer from the thermal process")
            break
        if message[0] == "log":
            lines.append(message[1])
        elif message[0] == "section":
            lines.append("section %d / %d at x = %.1f mm: T wall %.0f K" % (message[1], message[2], message[3], message[4]))
        elif message[0] == "done":
            ok = all(os.path.exists(os.path.join(folder, name)) for name in ("sim_data.csv", "params.csv", "sections_3d.html"))
            lines.append("done, warnings: %s" % message[3])
            break
        elif message[0] == "error":
            lines.append(message[1])
            break
    process.join(10)
    lines.append("SELF TEST " + ("PASSED" if ok else "FAILED"))
    with open(os.path.join(folder, "self_test.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


def main(argv=None):
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    # needed for the thermal simulation process in a packaged (frozen) app
    multiprocessing.freeze_support()
    argv = sys.argv if argv is None else argv
    if "--self-test" in argv:
        i = argv.index("--self-test")
        import tempfile
        return self_test(argv[i + 1] if len(argv) > i + 1 else tempfile.mkdtemp(prefix="tcd_self_test_"))

    from PySide6.QtWidgets import QApplication

    from . import themes
    from .main_window import MainWindow

    if sys.platform == "win32":
        # own taskbar entry, so the taskbar shows the icon of the app and not the one of python.exe when run from Python
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ThrustChamberDesigner")
    app = QApplication(argv)
    app.setApplicationName("Thrust Chamber Designer")
    app.setOrganizationName("Thrust Chamber Designer")
    # icons/app.ico is the icon of the window and the taskbar; the packaged exe takes the same file (packaging/*.spec)
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    window = MainWindow(app)
    themes.apply(app, window.settings.value("theme", themes.DEFAULT), window)
    window.redraw_plots()
    if len(argv) > 1 and argv[1].endswith(".json"):
        window.open_path(argv[1])
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
