# Copyright 2022 Ashley R. Thomas
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
r"""QueuedWorker.
"""

import os
import multiprocessing
import concurrent.futures
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, ProcessPoolExecutor
import queue
import logging
from .exception import exc_to_string


class QueuedSubprocessWorkManager:
    """QueuedWorker instances accept work via put_work() and deliver work results
    to callers of get_result(). Scheduled work is submitted to a subprocess by a seperate
    thread of this process, where that subprocess will queue the result when completed.
    Callers of get_result() dequeue those results.
    """

    def __init__(self, max_workers=None, max_queued_results=0):
        self.pending_work_queue = queue.Queue()  # Accessed in parent only.
        # [future] -> (func, args) # Accessed in parent only, two or more threads.
        self._work_in_progress = {}
        self._completed_results_queue = multiprocessing.Manager().Queue(
            max_queued_results
        )  # Accessed by all relevant processes.
        self._pending_results_count = multiprocessing.Value(
            "l", 0, lock=True
        )  # l==signed long, init to 0, with lock.
        self.thread_exec = ThreadPoolExecutor(
            max_workers=1
        )  # Accessed by parent process only.
        self._process_exec = ProcessPoolExecutor(
            max_workers=max_workers
        )  # Accessed by parent process only.
        self._schedule_worker_future = None
        self._is_shutdown = False  # Accessed by parent process only.

    def start(self):
        """Start this queued worker. This must be called before queuing any work."""
        if self._is_shutdown:
            raise ValueError(f"QueuedWorker has already been started and stopped.")
        if self._schedule_worker_future:
            raise ValueError(f"QueuedWorker has already been started.")
        self._schedule_worker_future = self.thread_exec.submit(
            QueuedSubprocessWorkManager._run_schedule_worker, self
        )

    @property
    def is_stopped(self):
        """True if this queued worker has been stopped, else False."""
        return self._is_shutdown

    def stop(self):
        """Stop this queued worker."""
        if self._is_shutdown:
            raise ValueError(f"QueuedWorker has already been started and stopped.")
        if not self._schedule_worker_future:
            raise ValueError(f"The schedule worker has not started.")
        self.put_work(None, None)
        self._schedule_worker_future.result()
        self._schedule_worker_future = None

    def _check_schedule_worker_futures(self, timeout=None):
        done, not_done = concurrent.futures.wait(
            self._work_in_progress.keys(), timeout, ALL_COMPLETED
        )
        # Observing an exception here should be rare as this detects
        # exceptions not caught by the process worker.
        for f in done:
            if f.exception():
                self._completed_results_queue.put((f.exception()))  # result=exception
            del self._work_in_progress[f]
        if len(not_done) != len(self._work_in_progress):
            msg = (
                f"Length of not_done does not match length of work_in_progress: "
                f"len(not_done)={len(not_done)} len(work_in_progress)={len(self._work_in_progress)}"
            )
            logging.error(msg)
            raise ValueError(msg)

    def _run_schedule_worker(self):
        try:
            while True:
                func, args = self.pending_work_queue.get(block=True)
                if func is None:
                    self._is_shutdown = True
                    break
                logging.debug(
                    f"_run_schedule_worker: submitting user work to subprocess..."
                )
                func_future = self._process_exec.submit(
                    QueuedSubprocessWorkManager._run_process_worker,
                    self._completed_results_queue,
                    func,
                    *args,
                )
                self._work_in_progress[func_future] = (func, args)
                self._check_schedule_worker_futures(timeout=1)
            logging.debug(
                f"_run_schedule_worker: shutting down, wait for work to complete."
            )
            self._check_schedule_worker_futures()
        except Exception as ex:
            logging.error(f"_run_schedule_worker fatal error: {exc_to_string(ex)}")
            raise

    @staticmethod
    def _run_process_worker(completed_results_queue, func, *args):
        pid = os.getpid()
        try:
            logging.debug(f"_run_process_worker: PID={pid}: before user func: {func}")
            result = func(*args)
            logging.debug(f"_run_process_worker: PID={pid}: after user func: {func}")
        except Exception as ex:
            logging.debug(
                f"_run_process_worker: PID={pid}: error during user func: {exc_to_string(ex)}"
            )
            result = ex
        logging.debug(
            f"_run_process_worker: PID={pid}: putting results: result={result} func={func} args={args}"
        )
        try:
            completed_results_queue.put(result)
        except Exception as ex:
            msg = f"_run_process_worker: PID={pid}: Fatal error attempting to enqueue result. {exc_to_string(ex)}"
            print(msg)
            logging.error(msg)

    @property
    def result_count_pending(self) -> int:
        """The count of pending results ready to be obtained
        via a call to get_result()
        """
        with self._pending_results_count.get_lock():
            return self._pending_results_count.value

    @property
    def are_results_pending(self) -> bool:
        """True if results will eventually be ready,
        False is no work is planned or in progress.
        """
        return self.result_count_pending > 0

    @property
    def is_result_ready(self) -> bool:
        """True if results are currently ready,
        False is no results are currently ready.
        """
        return not self._completed_results_queue.empty()

    def put_work(self, func, *args):
        """Enqueue work to be performed. Once completed,
        callers of get_result() can obtain the result.
        """
        if self._is_shutdown:
            raise ValueError(f"QueuedWorker has already been started and stopped.")
        if not self._schedule_worker_future:
            raise ValueError(f"Schedule worker has not been started.")
        if self._schedule_worker_future.done():
            if self._schedule_worker_future.exception():
                logging.error(
                    f"Schedule worker experienced a fatal error: ex={self._schedule_worker_future.exception()}"
                )
                raise self._schedule_worker_future.exception()
            raise ValueError(
                f"Schedule worker is not running despite having been started."
            )
        with self._pending_results_count.get_lock():
            self._pending_results_count.value += 1
        try:
            self.pending_work_queue.put(item=(func, args), block=True)
        except Exception as ex:
            logging.error(f"completed_results_queue.put error: {exc_to_string(ex)}")
            with self._pending_results_count.get_lock():
                self._pending_results_count.value -= 1
            self._completed_results_queue.put(None)
            raise

    def get_result(self, block=True, timeout=None, allow_without_pending=False):
        """Get next result. Caller should either check are_results_pending==True
        first, or know generally that put_work will occur, else caller will
        block forever unless timeout is specified.
        """
        if not self._schedule_worker_future:
            raise ValueError(f"Schedule worker has not been started.")
        if (
            self._schedule_worker_future.done()
            and self._schedule_worker_future.exception()
        ):
            logging.error(
                f"Schedule worker experienced a fatal error: {exc_to_string(self._schedule_worker_future.exception())}"
            )
            raise self._schedule_worker_future.exception()
        while True:
            pending = False
            with self._pending_results_count.get_lock():
                if self._pending_results_count.value > 0:
                    self._pending_results_count.value -= 1
                    pending = True
            if not allow_without_pending and not pending:
                raise ValueError(
                    f"Cannot get without pending work. Call put_work first, or use allow_without_pending=True"
                )
            try:
                result = self._completed_results_queue.get(block=block, timeout=timeout)
                # put_work enqueues None on exception during put.
                if result is None:
                    logging.error(
                        f"completed_results_queue.put error detected, adjusting pending_results_count and retrying."
                    )
                    if pending:
                        with self._pending_results_count.get_lock():
                            self._pending_results_count.value += 1
                    continue
                break
            except Exception as ex:
                if not isinstance(ex, queue.Empty):
                    logging.error(
                        f"completed_results_queue.get error: {exc_to_string(ex)}"
                    )
                if pending:
                    with self._pending_results_count.get_lock():
                        self._pending_results_count.value += 1
                raise
        return result
