import apricotpy
import heapq
import itertools
from . import core
from . import events
from . import futures
from . import objects
from . import serialisation
from . import utils

__all__ = ['BaseEventLoop']


class _CallbackLoop(object):
    def __init__(self, engine):
        self._engine = engine
        self._ready = []
        self._scheduled = []
        self._closed = False

    def _tick(self):
        # Handle scheduled callbacks that are ready
        end_time = self._engine.time() + self._engine.clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            self._insert_ready(handle)

        # Call ready callbacks
        todo = self._ready
        self._ready = []
        for handle in todo:
            if handle._cancelled:
                continue

            handle._run()

    def call_soon(self, fn, *args):
        handle = events.Handle(fn, args, self._engine)
        self._insert_ready(handle)
        return handle

    def call_later(self, delay, fn, *args):
        return self.call_at(self._engine.time() + delay, fn, *args)

    def call_at(self, when, fn, *args):
        timer = events.TimerHandle(when, fn, args, self._engine)
        heapq.heappush(self._scheduled, timer)
        timer._scheduled = True
        return timer

    def _insert_ready(self, handle):
        handle._when_ready = self._engine.time()
        heapq.heappush(self._ready, handle)

    def _insert_scheduled(self, timer):
        heapq.heappush(self._scheduled, timer)

    def _close(self):
        if self._closed:
            return

        self._closed = True
        del self._ready[:]
        del self._scheduled[:]


class BaseEventLoop(apricotpy.BaseEventLoop, objects.LoopObject):
    READY = 'READY'
    SCHEDULED = 'SCHEDULED'
    OBJECTS = 'OBJECTS'

    def __init__(self):
        super(BaseEventLoop, self).__init__(callback_loop=_CallbackLoop(self))

    def create_future(self):
        return futures.Future(self)

    def get_object(self, uuid):
        if uuid in self._objects:
            return self._objects[uuid]

        raise ValueError("Unknown object UUID '{}'".format(uuid))

    def get_callback_handle(self, uuid):
        for handle in itertools.chain(self._callback_loop._ready, self._callback_loop._scheduled):
            if handle.uuid == uuid:
                return handle

        raise ValueError("Unknown callback UUID '{}'".format(uuid))

    def get(self, uuid):
        try:
            return self.get_object(uuid)
        except ValueError:
            pass

        try:
            return self.get_callback_handle(uuid)
        except ValueError:
            pass

        # Out of options
        raise ValueError("Unknown UUID '{}'".format(uuid))

    def save_instance_state(self, out_state):
        super(BaseEventLoop, self).save_instance_state(out_state)

        out_state[self.READY] = self._callback_loop._ready
        out_state[self.SCHEDULED] = self._callback_loop._scheduled
        out_state[self.OBJECTS] = self._objects

    def load_instance_state(self, saved_state, loop):
        super(BaseEventLoop, self).load_instance_state(saved_state, loop)

        self._callback_loop._ready = saved_state[self.READY]
        self._callback_loop._scheduled = saved_state[self.SCHEDULED]
        self._objects = saved_state[self.OBJECTS]

    def _insert_object(self, obj):
        self._objects[obj.uuid] = obj

    def _insert_callback(self, handle):
        if isinstance(handle, events.TimerHandle):
            self._callback_loop._insert_scheduled(handle)
        elif isinstance(handle, events.Handle):
            self._callback_loop._insert_ready(handle)
        else:
            raise TypeError("Unsupported callback type given '{}'".format(handle))
