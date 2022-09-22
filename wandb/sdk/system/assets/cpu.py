import datetime
import multiprocessing as mp
from collections import deque
from typing import TYPE_CHECKING, Deque, List, Optional, cast

import psutil

from .interfaces import Metric, MetricType, MetricsMonitor
from . import asset_registry


if TYPE_CHECKING:
    from wandb.sdk.interface.interface_queue import InterfaceQueue
    from wandb.sdk.internal.settings_static import SettingsStatic


# CPU Metrics


class ProcessCpuPercent:
    # name = "process_cpu_percent"
    name = "cpu"
    metric_type = cast("gauge", MetricType)
    # samples: Deque[Tuple[datetime.datetime, float]]
    samples: Deque[float]

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.samples = deque([])

    def sample(self) -> None:
        # todo: this is what we'd eventually want to do
        # self.samples.append(
        #     (
        #         datetime.datetime.utcnow(),
        #         psutil.Process(self.pid).cpu_percent(),
        #     )
        # )
        self.samples.append(psutil.Process(self.pid).cpu_percent())

    def clear(self) -> None:
        self.samples.clear()

    def serialize(self) -> dict:
        # todo: create a statistics class with helper methods to compute
        #      mean, median, min, max, etc.
        aggregate = round(sum(self.samples) / len(self.samples), 2)
        return {self.name: aggregate}


class CpuPercent:
    # name = "cpu_percent"
    name = "gpu"
    metric_type = cast("gauge", MetricType)
    # samples: Deque[Tuple[datetime.datetime, List[float]]]
    samples: Deque[List[float]]

    def __init__(self, interval: Optional[float] = None) -> None:
        self.samples = deque([])
        self.interval = interval

    def sample(self) -> None:
        # self.samples.append(
        #     (
        #         datetime.datetime.utcnow(),
        #         psutil.cpu_percent(interval=self.interval, percpu=True),
        #     )
        # )
        self.samples.append(psutil.cpu_percent(interval=self.interval, percpu=True))  # type: ignore

    def clear(self) -> None:
        self.samples.clear()

    def serialize(self) -> dict:
        # fixme: ugly adapter to test things out
        num_cpu = len(self.samples[0])
        cpu_metrics = {}
        for i in range(num_cpu):
            aggregate_i = round(
                sum(sample[i] for sample in self.samples) / len(self.samples), 2
            )
            # fixme: fix this adapter, it's for testing 🤮🤮🤮🤮🤮
            cpu_metrics[f"gpu.{i}.gpu"] = aggregate_i

        return cpu_metrics


# todo: more metrics to consider:
# self._cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
# self._cpu_times = psutil.cpu_times_percent(interval=None, percpu=True)
# self._cpu_freq = psutil.cpu_freq(percpu=True)
# self._cpu_count = psutil.cpu_count(logical=False)
# self._cpu_count_logical = psutil.cpu_count(logical=True)
# self._cpu_load_avg = os.getloadavg()
# self._cpu_stats = psutil.cpu_stats()
# self._cpu_times = psutil.cpu_times()
# self._cpu_times_percent = psutil.cpu_times_percent()
# self._cpu_times_percent_per_cpu = psutil.cpu_times_percent(percpu=True)
# self._cpu_times_per_cpu = psutil.cpu_times(percpu=True)
# self._cpu_freq = psutil.cpu_freq()
# self._cpu_freq_per_cpu = psutil.cpu_freq(percpu=True)
# self._cpu_percent = psutil.cpu_percent(interval=None)
# self._cpu_percent_per_cpu = psutil.cpu_percent(interval=None, percpu=True)
# self._cpu_percent_interval = psutil.cpu_percent(interval=1)
# self._cpu_percent_interval_per_cpu = psutil.cpu_percent(interval=1, percpu=True)


@asset_registry.register
class CPU:
    def __init__(
        self,
        interface: "InterfaceQueue",
        settings: "SettingsStatic",
        shutdown_event: mp.Event,
    ) -> None:
        self.name: str = self.__class__.__name__.lower()
        self.metrics: List[Metric] = [
            ProcessCpuPercent(settings._stats_pid),
            CpuPercent(),
        ]
        self.metrics_monitor: "MetricsMonitor" = MetricsMonitor(
            self.metrics,
            interface,
            settings,
            shutdown_event,
        )

    @classmethod
    def is_available(cls) -> bool:
        """Return a new instance of the CPU metrics"""
        return True if psutil else False

    def probe(self) -> dict:
        asset_info = {
            "cpu_count": psutil.cpu_count(logical=False),
            "cpu_count_logical": psutil.cpu_count(logical=True),
        }
        return asset_info

    def start(self) -> None:
        self.metrics_monitor.start()

    def finish(self) -> None:
        self.metrics_monitor.finish()
