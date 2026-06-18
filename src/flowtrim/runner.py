from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from .models import LaneTask, MethodResult


def can_run_together(first: LaneTask, second: LaneTask) -> bool:
    if not first.read_only or not second.read_only:
        return False
    return first.write_set.isdisjoint(second.write_set)


def run_parallel(runners: dict[str, Callable[[], MethodResult]]) -> list[MethodResult]:
    with ThreadPoolExecutor(max_workers=len(runners)) as executor:
        futures = [executor.submit(runner) for runner in runners.values()]
        return [future.result() for future in futures]
