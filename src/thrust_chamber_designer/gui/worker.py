"""
Work that would block the window: the nozzle (a few seconds) runs in a thread, the thermal simulation and the throttle analysis
(minutes) in a separate process. A process can be stopped at any time with Cancel, and the window stays responsive while FiPy and
CoolProp keep a CPU busy.

The thermal process sends messages through a queue:
    ('log', text)                                       printed output of the simulation
    ('section', done, total, x [mm], T_wall_i [K], T_coolant [K], q [W/m^2])     after every section
    ('done', folder, geometry, warnings)                results are in folder
    ('error', traceback)

The throttle process sends 'log', 'error' and
    ('point', stage, done, total, ThrottleResult)       after every point of the map ('map') or of the schedules ('schedule')
    ('done', folder, map results, schedules)            results are in folder
"""

import multiprocessing
import queue as queue_module
import sys
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    """Runs function(*args) in the thread pool and emits finished(result) or failed(traceback)."""

    def __init__(self, function, *args):
        super().__init__()
        self.function = function
        self.args = args
        self.signals = _Signals()

    def run(self):
        try:
            result = self.function(*self.args)
        except Exception:
            self.signals.failed.emit(traceback.format_exc())
        else:
            self.signals.finished.emit(result)


_pool = None
_running = set()


def run_in_thread(function, *args, on_finished=None, on_failed=None):
    # one background thread for all tasks: NASA CEA is Fortran with global state and must not run twice at the same time
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(1)
    task = Task(function, *args)
    # the task and its signals must live until the result has reached the window: if Python collects them while the signal is
    # still queued, Qt delivers it to a deleted object and the app crashes
    task.setAutoDelete(False)
    _running.add(task)
    if on_finished is not None:
        task.signals.finished.connect(on_finished)
    if on_failed is not None:
        task.signals.failed.connect(on_failed)
    task.signals.finished.connect(lambda *_: _running.discard(task))
    task.signals.failed.connect(lambda *_: _running.discard(task))
    _pool.start(task)
    return task


class _QueueWriter:
    # stdout of the thermal process, line by line to the window
    def __init__(self, queue):
        self.queue = queue
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.queue.put(("log", line))
        return len(text)

    def flush(self):
        if self.buffer:
            self.queue.put(("log", self.buffer))
            self.buffer = ""


def thermal_job(design_dict, folder, queue, plot_theme="dark"):
    """Target of the thermal process: nozzle, thermal simulation and the files of the results in folder."""
    sys.stdout = sys.stderr = _QueueWriter(queue)
    try:
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        import matplotlib
        matplotlib.use("Agg")
        from .. import pipeline
        from ..core.design import Design
        from ..thermal.plots import Plotting1D
        from ..thermal import creep, ratchet
        from ..thermal.stress import summary

        design = Design.from_dict(design_dict)
        nd = pipeline.design_nozzle(design)
        pipeline.write_nozzle_outputs(nd, folder)
        setup = pipeline.build_thermal(nd, folder)
        print("Thermal simulation of %d sections, cell size %.3g mm" % (len(setup.geometry), setup.settings.cell_size * 1e3))
        out = setup.output

        def progress(done, total, idx):
            queue.put(("section", done, total, float(setup.geometry[idx, 0] * 1e3), float(out.T_wall_i[idx]), float(out.T_c[idx]),
                       float(out.q[idx])))

        sim = pipeline.run_thermal(setup, progress)
        summary(out, setup.material, design.thermal.ambient_temperature)
        creep.summary(out, setup.material, design.thermal.firing_time, design.thermal.firings)
        ratchet.summary(out, setup.material, design.thermal.firing_time, design.thermal.firings)
        try:
            Plotting1D(save_path=folder, geometry=setup.geometry, cooling_geom=setup.cooling_geom, boiling=design.thermal.boiling,
                       post_chf=design.thermal.post_chf, save=False).section_3d_plot(include_plotlyjs=True, theme=plot_theme)
        except Exception:
            print("The 3D view could not be made:\n" + traceback.format_exc())
        design.save(folder + "/design.json")
        cg = setup.cooling_geom
        geometry = {"contour": setup.geometry, "beta": cg.beta, "psi_c": cg.psi_c, "psi_w": cg.psi_w, "h_c": cg.h_c,
                    "t_w_i": cg.t_w_i, "t_w_o": cg.t_w_o, "twist": cg.twist, "n_channels": cg.n_channels}
        sys.stdout.flush()
        queue.put(("done", folder, geometry, pipeline.thermal_warnings(setup, sim) + nd.warnings))
    except Exception:
        sys.stdout.flush()
        queue.put(("error", traceback.format_exc()))


def throttle_job(design_dict, folder, queue, stop, jobs=None):
    """Target of the throttle process: nozzle, map and schedules, with the files of the results in folder. The points are solved by worker
    processes of this process, so that it can not be a daemon, and stop (an Event) ends it with the workers."""
    sys.stdout = sys.stderr = _QueueWriter(queue)
    try:
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        import matplotlib
        matplotlib.use("Agg")
        from .. import pipeline
        from ..core.design import Design
        from ..thermal import throttle

        design = Design.from_dict(design_dict)
        nd = pipeline.design_nozzle(design)
        for note in nd.warnings:
            print("WARNING:", note)
        design.save(folder + "/design.json")

        def progress(stage, done, total, result):
            queue.put(("point", stage, done, total, result))

        try:
            map_results, schedules = throttle.run(nd, folder, jobs, True, progress, stop.is_set)
        except throttle.ThrottleCancelled:
            return
        sys.stdout.flush()
        queue.put(("done", folder, map_results, schedules))
    except Exception:
        sys.stdout.flush()
        queue.put(("error", traceback.format_exc()))


class _ProcessRun(QObject):
    """A job in a separate process, which reports through a queue to signals for the window."""
    log = Signal(str)
    done = Signal(str, object, object)
    failed = Signal(str)
    text = "The job"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.queue = None
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)

    @property
    def running(self):
        return self.process is not None and self.process.is_alive()

    def cancel(self):
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join(2)
        self._stop()

    def _stop(self):
        self.timer.stop()
        self.process = None

    def _message(self, message):
        # messages other than log, done and error
        pass

    def _poll(self):
        while True:
            alive = self.process is not None and self.process.is_alive()
            try:
                # once the process has ended, wait a little for the last messages still on their way through the pipe
                message = self.queue.get_nowait() if alive else self.queue.get(timeout=1.0)
            except queue_module.Empty:
                if not alive and self.process is not None:
                    code = self.process.exitcode
                    self._stop()
                    self.failed.emit("%s stopped without a result (exit code %s)" % (self.text, code))
                return
            kind = message[0]
            if kind == "log":
                self.log.emit(message[1])
            elif kind == "done":
                self._stop()
                self.done.emit(*message[1:])
                return
            elif kind == "error":
                self._stop()
                self.failed.emit(message[1])
                return
            else:
                self._message(message)


class ThermalRun(_ProcessRun):
    """The thermal simulation in a separate process, with signals for the window."""
    section = Signal(int, int, float, float, float, float)
    text = "The thermal simulation"

    def start(self, design, folder, plot_theme="dark"):
        # spawn, not fork: a forked copy of a process with Qt in it is not safe
        ctx = multiprocessing.get_context("spawn")
        self.queue = ctx.Queue()
        self.process = ctx.Process(target=thermal_job, args=(design.to_dict(), folder, self.queue, plot_theme), daemon=True)
        self.process.start()
        self.timer.start()

    def _message(self, message):
        if message[0] == "section":
            self.section.emit(*message[1:])


class ThrottleRun(_ProcessRun):
    """The throttle analysis in a separate process, with signals for the window."""
    point = Signal(str, int, int, object)
    text = "The throttle analysis"

    def start(self, design, folder, jobs=None):
        ctx = multiprocessing.get_context("spawn")
        self.queue = ctx.Queue()
        self.stop_event = ctx.Event()
        self.process = ctx.Process(target=throttle_job, args=(design.to_dict(), folder, self.queue, self.stop_event, jobs))
        self.process.start()
        self.timer.start()

    def cancel(self):
        # the process stops its workers itself. Terminating it at once would leave them running
        if self.process is not None and self.process.is_alive():
            self.stop_event.set()
            self.process.join(5)
        super().cancel()

    def _message(self, message):
        if message[0] == "point":
            self.point.emit(*message[1:])


def results_geometry(design):
    """Contour and channel geometry of the thermal model of a design, to show results of an earlier run (same dict as 'done')."""
    from .. import pipeline

    nd = pipeline.design_nozzle(design)
    chamber, cg = pipeline.cooling_geometry(nd)
    return nd, {"contour": chamber.geometry, "beta": cg.beta, "psi_c": cg.psi_c, "psi_w": cg.psi_w, "h_c": cg.h_c, "t_w_i": cg.t_w_i,
                "t_w_o": cg.t_w_o, "twist": cg.twist, "n_channels": cg.n_channels}
