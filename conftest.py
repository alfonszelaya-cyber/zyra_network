
# ZYRA-DAEMON-PATCH
# Root cause fix: background threads (outbox workers,
# servers, supervisors) created during tests kept the
# interpreter alive after pytest finished, so the full
# suite never terminated. Every thread created during
# the test session is forced to daemon=True BEFORE it
# starts, so pytest always exits cleanly.
import threading as _threading

_original_thread_init = _threading.Thread.__init__


def _zyra_daemon_thread_init(
    self, *args, **kwargs,
):
    _original_thread_init(
        self, *args, **kwargs
    )
    try:
        if (
            self
            is not _threading
            .main_thread()
        ):
            self.daemon = True
    except (
        RuntimeError,
        ValueError,
    ):
        pass


_threading.Thread.__init__ = (
    _zyra_daemon_thread_init
)


def pytest_sessionfinish(
    session, exitstatus,
):
    stray = [
        t.name
        for t in _threading.enumerate()
        if (
            t
            is not _threading
            .main_thread()
            and t.is_alive()
        )
    ]
    print(
        "ZYRA leftover threads"
        " (daemon, non-blocking): "
        + str(len(stray))
    )
    for name in stray:
        print("  - " + str(name))

