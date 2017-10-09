import heapq
import itertools
import logging
import os
import sys
import threading
import time
import traceback
from collections import deque

from apricotpy.events import AbstractEventLoop
from . import events
from . import futures
from . import messages

__all__ = ['BaseEventLoop']

_LOGGER = logging.getLogger(__name__)
_DEBUG_ENV_VAR = 'PYTHONAPRICOTDEBUG'


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
        handle = events.Handle(fn, args, self._event_loop)
        self._ready.append(handle)
        return handle

    def call_later(self, delay, fn, *args):
        return self.call_at(self._event_loop.time() + delay, fn, *args)

    def call_at(self, when, fn, *args):
        timer = events.TimerHandle(when, fn, args, self._event_loop)
        heapq.heappush(self._scheduled, timer)
        return timer

    def _close(self):
        if self._closed:
            return

        self._closed = True
        self._ready.clear()
        del self._scheduled[:]


class _RunContext(object):
    def __init__(self, loop):
        self._loop = loop

    def __enter__(self):
        if self._loop.is_running():
            raise RuntimeError('This event loop is already running')
        self._thread_id = threading.current_thread().ident
        events._push_running_loop(self._loop)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stopping = False
        self._thread_id = None
        assert events._pop_running_loop() is self._loop


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
        self._exception_handler = None
        self.set_debug((not sys.flags.ignore_environment
                        and bool(os.environ.get(_DEBUG_ENV_VAR))))
        self._current_handle = None

        self.__mailman = messages.Mailman(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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
        with _RunContext(self):
            try:
                while not self._stopping:
                    self._run_once()
            finally:
                self._stopping = False

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

        awaitable.remove_done_callback(self._run_until_complete_cb)
        if not awaitable.done():
            raise RuntimeError('Event loop stopped before Future completed.')

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
        with _RunContext(self):
            self._run_once()

    def time(self):
        return time.time()

    def messages(self):
        return self.__mailman

    # region Objects
    def create(self, object_type, *args, **kwargs):
        kwargs['loop'] = self
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

        if self._debug:
            _LOGGER.debug("Close %r", self)

        self._stopping = False
        self._callback_loop._close()

        self._objects = None
        self._object_factory = None

        self._thread_id = None

        self.__mailman = None

    # region Errors
    def get_exception_handler(self):
        """Return an exception handler, or None if the default one is in use.
        """
        return self._exception_handler

    def set_exception_handler(self, handler):
        """Set handler as the new event loop exception handler.
        If handler is None, the default exception handler will
        be set.
        If handler is a callable object, it should have a
        signature matching '(loop, context)', where 'loop'
        will be a reference to the active event loop, 'context'
        will be a dict object (see `call_exception_handler()`
        documentation for details about context).
        """
        if handler is not None and not callable(handler):
            raise TypeError('A callable object or None is expected, '
                            'got {!r}'.format(handler))
        self._exception_handler = handler

    def default_exception_handler(self, context):
        """Default exception handler.
        This is called when an exception occurs and no exception
        handler is set, and can be called by a custom exception
        handler that wants to defer to the default behavior.
        The context parameter has the same meaning as in
        `call_exception_handler()`.
        """
        message = context.get('message')
        if not message:
            message = 'Unhandled exception in event loop'

        exception = context.get('exception')
        if exception is not None:
            exc_info = (type(exception), exception, exception.__traceback__)
        else:
            exc_info = False

        if ('source_traceback' not in context
            and self._current_handle is not None
            and self._current_handle._source_traceback):
            context['handle_traceback'] = self._current_handle._source_traceback

        log_lines = [message]
        for key in sorted(context):
            if key in {'message', 'exception'}:
                continue
            value = context[key]
            if key == 'source_traceback':
                tb = ''.join(traceback.format_list(value))
                value = 'Object created at (most recent call last):\n'
                value += tb.rstrip()
            elif key == 'handle_traceback':
                tb = ''.join(traceback.format_list(value))
                value = 'Handle created at (most recent call last):\n'
                value += tb.rstrip()
            else:
                value = repr(value)
            log_lines.append('{}: {}'.format(key, value))

        _LOGGER.error('\n'.join(log_lines), exc_info=exc_info)

    def call_exception_handler(self, context):
        """Call the current event loop's exception handler.
        The context argument is a dict containing the following keys:
        - 'message': Error message;
        - 'exception' (optional): Exception object;
        - 'future' (optional): Future instance;
        - 'handle' (optional): Handle instance;
        - 'protocol' (optional): Protocol instance;
        - 'transport' (optional): Transport instance;
        - 'socket' (optional): Socket instance;
        - 'asyncgen' (optional): Asynchronous generator that caused
                                 the exception.
        New keys maybe introduced in the future.
        Note: do not overload this method in an event loop subclass.
        For custom exception handling, use the
        `set_exception_handler()` method.
        """
        if self._exception_handler is None:
            try:
                self.default_exception_handler(context)
            except Exception:
                # Second protection layer for unexpected errors
                # in the default implementation, as well as for subclassed
                # event loops with overloaded "default_exception_handler".
                _LOGGER.error('Exception in default exception handler',
                              exc_info=True)
        else:
            try:
                self._exception_handler(self, context)
            except Exception as exc:
                # Exception in the user set custom exception handler.
                try:
                    # Let's try default handler.
                    self.default_exception_handler({
                        'message': 'Unhandled error in exception handler',
                        'exception': exc,
                        'context': context,
                    })
                except Exception:
                    # Guard 'default_exception_handler' in case it is
                    # overloaded.
                    _LOGGER.error('Exception in default exception handler '
                                  'while handling an unexpected error '
                                  'in custom exception handler',
                                  exc_info=True)

    # endregion

    # region Debugging
    def get_debug(self):
        return self._debug

    def set_debug(self, enabled):
        self._debug = enabled

    # endregion

    def _run_once(self):
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
