"""Bounds shared by ordinary execution and replay in the local demo process."""
from contextlib import contextmanager
import sys
import threading

MEMORY_BYTES = 128 * 1024 * 1024
_EXECUTIONS = threading.BoundedSemaphore(2)


class ExecutionBusy(Exception):
    pass


@contextmanager
def execution_slot():
    if not _EXECUTIONS.acquire(blocking=False):
        raise ExecutionBusy('执行器繁忙，请稍后重试')
    try:
        yield
    finally:
        _EXECUTIONS.release()


def apply_worker_limits(timeout):
    # The supported Docker runtime is Linux. Native Windows retains the parent
    # wall-clock deadline, but does not provide these Linux resource limits.
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
