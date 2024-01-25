import asyncio
from dataclasses import dataclass
import datetime
import logging
from typing import Any, Awaitable, Dict, List, Optional, TypedDict

from wandb.apis.internal import Api
from wandb.sdk.launch.utils import event_loop_thread_exec


@dataclass
class JobSetSpec: # (TypedDict):
    name: str
    entity_name: str
    project_name: Optional[str]

@dataclass
class JobSetDiff:
    version: int
    complete: bool
    metadata: Dict[str, Any]
    upsert_jobs: List[Dict[str, Any]]
    remove_jobs: List[str]


JobSetId = str


def create_job_set(spec: JobSetSpec, api: Api, agent_id: str, logger: logging.Logger):
    # Retrieve the job set via Api.get_job_set_diff_by_spec
    job_set_response = api.get_job_set_by_spec(
        job_set_name=spec["name"],
        entity_name=spec["entity_name"],
        project_name=spec["project_name"],
    )
    return JobSet(api, job_set_response, agent_id, logger)


class JobSet:
    def __init__(
        self, api: Api, job_set: Dict[str, Any], agent_id: str, logger: logging.Logger
    ):
        self.api = api
        self.agent_id = agent_id

        self.id = job_set.pop("id")
        self.name = job_set.pop("name")
        self._metadata = job_set["metadata"]
        self._lock = asyncio.Lock()

        self._logger = logger
        self._jobs: Dict = dict()
        self._ready_event = asyncio.Event()
        self._updated_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._done_event = asyncio.Event()
        self._poll_now_event = asyncio.Event()
        self._next_poll_interval = 5

        self._task = None
        self._last_state: Optional[JobSetDiff] = None

    @property
    def lock(self):
        return self._lock

    @property
    def jobs(self):
        return self._jobs.copy()

    @property
    def metadata(self):
        return self._metadata.copy()

    @property
    async def wait_for_done(self):
        return await self._done_event.wait()

    async def wait_for_update(self):
        self._updated_event.clear()
        await self._updated_event.wait()

    @property
    def job_set_diff_version(self):
        if self._last_state is None:
            return -1
        return self._last_state.version
    
    async def _poll_now_task(self):
        return await self._poll_now_event.wait()

    async def _sync_loop(self):
        while not self._shutdown_event.is_set():
            await self._sync()
            wait_task = asyncio.create_task(self._poll_now_task())
            await asyncio.wait(
                [wait_task],
                timeout=self._next_poll_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._poll_now_event.is_set():
                self._poll_now_event.clear()
        self._logger.debug(f"[JobSet {self.name or self.id}] Sync loop exited.")
        self._done_event.set()

    async def _sync(self):
        self._logger.debug(f"[JobSet {self.name or self.id}] Updating...")
        next_state = await self._refresh_job_set()
        self._logger.debug(f"[JobSet nextstate] [{datetime.datetime.now().isoformat()}] {next_state}")

        # just grabbed a diff from the server, now to add to our local state
        self._last_state = next_state

        # TODO: make this sicker
        # self._metadata = next_state.metadata
        async with self.lock:
            for job in self._last_state.upsert_jobs:
                self._jobs[job["id"]] = job
                self._logger.debug(
                    f'[JobSet {self.name or self.id}] Updated Job {job["id"]}'
                )

            for job_id in self._last_state.remove_jobs:
                if not self._jobs.pop(job_id, False):
                    self._logger.error(
                        f"[JobSet {self.name or self.id}] Deleted Job {job_id}, but it did not exist"
                    )
                    continue
                self._logger.debug(
                    f"[JobSet {self.name or self.id}] Deleted Job {job_id}"
                )

        self._logger.debug(f"[JobSet {self.name or self.id}] Done.")
        self._ready_event.set()
        self._updated_event.set()

    async def _refresh_job_set(self) -> JobSetDiff:
        get_job_set_diff_by_id = event_loop_thread_exec(self.api.get_job_set_diff_by_id)
        diff = await get_job_set_diff_by_id(
            self.id, self.job_set_diff_version, self.agent_id
        )
        return JobSetDiff(
            version=diff["version"],
            complete=diff["complete"],
            metadata=diff["metadata"],
            upsert_jobs=diff["upsertJobs"],
            remove_jobs=diff["removeJobs"],
        )

    def _poll_now(self):
        self._poll_now_event.set()

    def start_sync_loop(self, loop: asyncio.AbstractEventLoop):
        if self._task is None:
            self._loop = loop
            self._shutdown_event.clear()
            self._logger.debug(f"[JobSet {self.name or self.id}] Starting sync loop")
            self._task = self._loop.create_task(self._sync_loop())
        else:
            raise RuntimeError("Tried to start JobSet but already started")

    def stop_sync_loop(self):
        if self._task is not None:
            self._logger.debug(f"[JobSet {self.name or self.id}] Stopping sync loop")
            self._shutdown_event.set()
            self._poll_now_event.set()
            self._task = None
        else:
            raise RuntimeError("Tried to stop JobSet but not started")

    async def ready(self) -> None:
        await self._ready_event.wait()

    async def lease_job(self, job_id: str) -> Awaitable[bool]:
        lease_job_set_item = event_loop_thread_exec(self.api.lease_job_set_item)
        result = await lease_job_set_item(self.id, job_id, self.agent_id)
        if result:
            self._poll_now()
        return result

    async def ack_job(self, job_id: str, run_name: str) -> Awaitable[bool]:
        ack_job_set_item = event_loop_thread_exec(self.api.ack_job_set_item)
        result = await ack_job_set_item(self.id, job_id, self.agent_id, run_name)
        if result:
            self._poll_now()
        return result

    async def fail_job(
        self,
        job_id: str,
        message: str,
        stage: str,
        file_paths: Optional[List[str]] = None,
    ) -> Awaitable[bool]:
        fail_run_queue_item = event_loop_thread_exec(self.api.fail_run_queue_item)
        result = await fail_run_queue_item(job_id, message, stage, file_paths)
        if result:
            self._poll_now()
        return result
