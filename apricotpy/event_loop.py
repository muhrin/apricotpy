from abc import ABCMeta, abstractmethod
from collections import deque
import logging
import heapq
import itertools
import time
import threading

from . import futures
from . import events
from . import messages

_LOGGER = logging.getLogger(__name__)

__all__ = ['BaseEventLoop']


class AbstractEventLoop(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def create_future(self):
        """

        :return: A new future
        :rtype: :class:`futures.Future`
        """
        pass

    @abstractmethod
    def run_forever(self):
        pass

    @abstractmethod
    def run_until_complete(self, future):
        pass

    @abstractmethod
    def call_soon(self, fn, *args):
        pass

    @abstractmethod
    def call_later(self, delay, callback, *args):
        """
        Schedule callback to be called after the given `delay` in seconds.
         
        :param delay: The callback delay
        :type delay: float
        :param callback: The callback to call
        :param args: The callback arguments
        :return: A callback handle
        :rtype: :class:`events.Handle`
        """
        pass

    @abstractmethod
    def call_at(self, when, callback, *args):
        """
        Schedule a callback to to be called at a given time

        :param when: The time when to call
        :type when: float
        :param callback: The callback to call
        :param args: The callback arguments
        :return: A callback handle
        :rtype: :class:`events.Handle`
        """
        pass

    @abstractmethod
    def time(self):
        pass

    @abstractmethod
    def messages(self):
        pass

    # region Objects
    @abstractmethod
    def get_object(self, uuid):
        pass

    @abstractmethod
    def objects(self, obj_type=None):
        """
        Get the objects in the event loop.  Optionally filer for loop objects of
        a given type.
        
        :param obj_type: The loop object class to filter for. 
        :return: A list of the found objects.
        """
        pass

    @abstractmethod
    def create(self, object_type, *args, **kwargs):
        """
        Create a task and schedule it to be inserted into the loop.
        
        :param object_type: The task identifier 
        :param args: (optional) positional arguments to the task
        :param kwargs: (optional) keyword arguments to the task
        
        :return: The task object
        """
        pass

    @abstractmethod
    def create_inserted(self, object_type, *args, **kwargs):
        """
        Create a task and schedule it to be inserted into the loop.

        :param object_type: The task identifier 
        :param args: (optional) positional arguments to the task
        :param kwargs: (optional) keyword arguments to the task

        :return: The future corresponding to the insertion of the object into the loop
        """
        pass

    @abstractmethod
    def remove(self, loop_object):
        """
        Schedule an object to be removed an object from the event loop.

        :param loop_object: The object to remove 
        :return: A future corresponding to the removal of the object
        """
        pass

    @abstractmethod
    def set_object_factory(self, factory):
        """
        Set the factory used by :class:`AbstractEventLoop.create_task()`.
        
        If `None` then the default will be set.
        
        The factory should be a callabke with signature matching `(loop, task, *args, **kwargs)`
        where task is some task identifier and positional and keyword arguments
        can be supplied and it returns the :class:`Task` instance.
        
        :param factory: The task factory 
        """
        pass

    @abstractmethod
    def get_object_factory(self):
        """
        Get the task factory currently in use.  Returns `None` if the default is
        being used.
        
        :return: The task factory
        """
        pass

        # endregion

    @abstractmethod
    def close(self):
        """Shutdown the event loop"""
        pass


class _CallbackLoop(object):
    def __init__(self, event_loop):
        self._event_loop = event_loop
        self._ready = deque()
        self._scheduled = []
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
            self._ready.append(handle)

        # Call ready callbacks
        todo = len(self._ready)
        for _ in range(todo):
            handle = self._ready.popleft()
            if handle._cancelled:
                continue

            handle._run()

    def call_soon(self, fn, *args):
        handle = events.Handle(fn, args, self)
        self._ready.append(handle)
        return handle

    def call_later(self, delay, fn, *args):
        return self.call_at(self._event_loop.time() + delay, fn, *args)

    def call_at(self, when, fn, *args):
        timer = events.TimerHandle(when, fn, args, self)
        heapq.heappush(self._scheduled, timer)
        return timer

    def _close(self):
        if self._closed:
            return

        self._closed = True
        self._ready.clear()
        del self._scheduled[:]


class BaseEventLoop(AbstractEventLoop):
    def __init__(self, callback_loop=None):
        super(BaseEventLoop, self).__init__()

        self._stopping = False
        if callback_loop is None:
            self._callback_loop = _CallbackLoop(self)
        else:
            self._callback_loop = callback_loop

        self._objects = {}
        self._object_factory = None

        self._thread_id = None

        self.__mailman = messages.Mailman(self)

    @property
    def clock_resolution(self):
        return 0.1

    def is_running(self):
        """
        Returns True if the event loop is running.
        
        :return: True if running, False otherwise
        :rtype: bool
        """
        return self._thread_id is not None

    def create_future(self):
        return futures.Future(self)

    def run_forever(self):
        self._thread_id = threading.current_thread().ident

        try:
            while not self._stopping:
                self._tick()

        finally:
            self._stopping = False
            self._thread_id = None

    def run_until_complete(self, awaitable):
        """
        :param awaitable: The awaitable
        :type awaitable: :class:`futures.Awaitable`
        :return: The result of the awaitable
        """
        assert isinstance(awaitable, futures.Awaitable), "Must supply Awaitable object"

        if not awaitable.done():
            awaitable.add_done_callback(self._run_until_complete_cb)
            self.run_forever()

        return awaitable.result()

    def call_soon(self, fn, *args):
        """
        Call a callback function on the next tick

        :param fn: The callback function
        :param args: The function arguments
        :return: A callback handle
        :rtype: :class:`events.Handle`
        """
        return self._callback_loop.call_soon(fn, *args)

    def call_later(self, delay, fn, *args):
        return self._callback_loop.call_later(delay, fn, *args)

    def call_at(self, when, callback, *args):
        return self._callback_loop.call_at(when, callback, *args)

    def objects(self, obj_type=None):
        # Filter the type if necessary
        if obj_type is not None:
            return [obj for obj in self._objects.itervalues() if isinstance(obj, obj_type)]
        else:
            return self._objects.values()

    def get_object(self, uuid):
        try:
            return self._objects[uuid]
        except KeyError:
            raise ValueError("Unknown uuid")

    def stop(self):
        """
        Stop the running event loop. 
        """
        self._stopping = True

    def tick(self):
        self._thread_id = threading.current_thread().ident
        try:
            self._tick()
        finally:
            self._thread_id = None

    def time(self):
        return time.time()

    def messages(self):
        return self.__mailman

    # region Objects
    def create(self, object_type, *args, **kwargs):
        loop_object = self._create(object_type, *args, **kwargs)

        self.insert(loop_object)
        return loop_object

    def create_inserted(self, object_type, *args, **kwargs):
        loop_object = self._create(object_type, *args, **kwargs)
        return self.insert(loop_object)

    def insert(self, loop_object):
        self.messages().send("loop.object.{}.inserting".format(loop_object.uuid), loop_object.uuid)
        return loop_object.insert_into(self)

    def remove(self, loop_object):
        self.messages().send("loop.object.{}.removing".format(loop_object.uuid), loop_object.uuid)
        return loop_object.remove(self)

    def set_object_factory(self, factory):
        self._object_factory = factory

    def get_object_factory(self):
        return self._object_factory

    # endregion

    def close(self):
        assert not self.is_running(), "Can't close a running loop"

        self._stopping = False
        self._callback_loop._close()

        self._objects = None
        self._object_factory = None

        self._thread_id = None

        self.__mailman = None

    def _tick(self):
        self._callback_loop._tick()

    def _run_until_complete_cb(self, fut):
        self.stop()

    def _create(self, object_type, *args, **kwargs):
        if self._object_factory is None:
            obj = object_type(*args, **kwargs)
        else:
            obj = self._object_factory(self, object_type, *args, **kwargs)

        uuid = obj.uuid
        # self._objects[uuid] = obj
        self.messages().send("loop.object.{}.created".format(uuid), uuid)

        return obj

    def _insert(self, obj, fut=None):
        uuid = obj.uuid
        self._objects[uuid] = obj
        obj.on_loop_inserted(self)
        if fut is not None:
            fut.set_result(obj)
        self.messages().send("loop.object.{}.inserted".format(uuid), uuid)

    def _remove(self, obj, fut):
        uuid = obj.uuid
        try:
            assert obj is self._objects[obj.uuid], "Asked to remove different object with same uuid!"
        except KeyError:
            fut.set_exception(ValueError("Unknown uuid '{}', object='{}'".format(uuid, obj.__class__.__name__)))
        except BaseException as e:
            fut.set_exception(e)
        else:
            obj.on_loop_removed()

            # Cancel any callbacks to the object
            for cb in itertools.chain(self._callback_loop._ready, self._callback_loop._scheduled):
                try:
                    if cb._fn.__self__ is obj:
                        cb.cancel()
                        _LOGGER.info("Cancelled callback to '{}' because the loop "
                                     "object was removed".format(cb._fn))
                except AttributeError:
                    pass

            self._objects.pop(uuid)
            fut.set_result(uuid)
            self.messages().send("loop.object.{}.removed".format(uuid), uuid)

    def _create_handle(self, fn, args):
        return events.Handle(fn, args, self)

    def _create_timer_handle(self, when, fn, args):
        return events.TimerHandle(when, fn, args, self)
