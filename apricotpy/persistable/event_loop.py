import apricotpy
import apricotpy.messages
import heapq
import logging
from . import core
from . import events
from . import futures
from . import objects

_LOGGER = logging.getLogger(__name__)

__all__ = ['BaseEventLoop']


class _CallbackLoop(object):
    def __init__(self, engine):
        self._event_loop = engine
        self._ready = []
        self._scheduled = []
        self._active_object = None
        self._closed = False

    def _tick(self):
        # Handle scheduled callbacks that are ready
        end_time = self._event_loop.time() + self._event_loop.clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            self._insert_ready(handle)

        # Call ready callbacks
        todo = len(self._ready)
        for _ in range(todo):
            handle = self._ready.pop(0)
            if handle._cancelled:
                continue
            try:
                self._active_object = events._get_loop_persistable_from_fn(handle._fn)
                if self._event_loop.get_debug():
                    try:
                        self._current_handle = handle
                        t0 = self._event_loop.time()
                        handle._run()
                        dt = self._event_loop.time() - t0
                        if dt >= self._event_loop.slow_callback_duration:
                            _LOGGER.warning('Executing %s took %.3f seconds',
                                            handle, dt)
                    finally:
                        self._current_handle = None
                else:
                    handle._run()
            finally:
                self._active_object = None

    def call_soon(self, fn, *args):
        owner = self._get_owner(fn)
        handle = events.Handle(fn, args, self._event_loop, owner)
        self._insert_ready(handle)
        return handle

    def call_later(self, delay, fn, *args):
        return self.call_at(self._event_loop.time() + delay, fn, *args)

    def call_at(self, when, fn, *args):
        owner = self._get_owner(fn)
        timer = events.TimerHandle(when, fn, args, self._event_loop, owner)
        heapq.heappush(self._scheduled, timer)
        timer._scheduled = True
        return timer

    def _insert_ready(self, handle):
        """
        :param handle: The callback handle 
        :type handle: :class:`events.Handle`
        """
        handle._when = self._event_loop.time()
        heapq.heappush(self._ready, handle)

    def _insert_scheduled(self, timer):
        heapq.heappush(self._scheduled, timer)

    def _close(self):
        if self._closed:
            return

        self._closed = True
        del self._ready[:]
        del self._scheduled[:]

    def _get_owner(self, fn):
        owner = events._get_loop_persistable_from_fn(fn)
        if owner is None:
            owner = self._active_object
        if owner is None:
            owner = self._event_loop
        return owner


class BaseEventLoop(apricotpy.BaseEventLoop, core.LoopPersistable):
    READY = 'READY'
    SCHEDULED = 'SCHEDULED'
    OBJECTS = 'OBJECTS'

    def __init__(self):
        super(BaseEventLoop, self).__init__(callback_loop=_CallbackLoop(self))

    def create_future(self):
        return futures.Future(self)

    def save_instance_state(self, out_state):
        super(BaseEventLoop, self).save_instance_state(out_state)

        out_state[self.READY] = tuple(self._callback_loop._ready)
        out_state[self.SCHEDULED] = tuple(self._callback_loop._scheduled)

    def load_instance_state(self, saved_state):
        super(BaseEventLoop, self).load_instance_state(saved_state)

        self._callback_loop = _CallbackLoop(self)
        self._callback_loop._ready = list(saved_state[self.READY])
        self._callback_loop._scheduled = list(saved_state[self.SCHEDULED])

        # Runtime state stuff
        self._stopping = False
        self._object_factory = None
        self.__mailman = apricotpy.messages.Mailman(self)

    def _insert_callback(self, handle):
        if isinstance(handle, events.TimerHandle):
            self._callback_loop._insert_scheduled(handle)
        elif isinstance(handle, events.Handle):
            self._callback_loop._insert_ready(handle)
        else:
            raise TypeError("Unsupported callback type given '{}'".format(handle))

    def _get_owning_callback_handles(self, loop_persistable):
        return (handle for handle in self._callback_loop._ready
                if handle._owner is loop_persistable)
