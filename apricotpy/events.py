import abc
import functools
import inspect
import os

import reprlib
import sys
import threading
import traceback

from future.utils import with_metaclass

__all__ = ['AbstractEventLoopPolicy',
           'AbstractEventLoop',
           'Handle', 'TimerHandle',
           'get_event_loop_policy', 'set_event_loop_policy',
           'get_event_loop', 'set_event_loop', 'new_event_loop',
           '_push_running_loop', '_pop_running_loop', '_get_running_loop',
           ]


def _get_function_source(func):
    if hasattr(func, '__wrapped__'):
        func = func.__wrapped__
    if inspect.isfunction(func):
        code = func.__code__
        return code.co_filename, code.co_firstlineno
    if isinstance(func, functools.partial):
        return _get_function_source(func.func)

    return None


def _format_args_and_kwargs(args, kwargs):
    """
    Format function arguments and keyword arguments.
    Special case for a single parameter: ('hello',) is formatted as ('hello').
    """
    # use reprlib to limit the length of the output
    items = []
    if args:
        items.extend(reprlib.repr(arg) for arg in args)
    if kwargs:
        items.extend('{}={}'.format(k, reprlib.repr(v))
                     for k, v in kwargs.items())
    return '(' + ', '.join(items) + ')'


def _format_callback(func, args, kwargs, suffix=''):
    if isinstance(func, functools.partial):
        suffix = _format_args_and_kwargs(args, kwargs) + suffix
        return _format_callback(func.func, func.args, func.keywords, suffix)

    if hasattr(func, '__qualname__'):
        func_repr = getattr(func, '__qualname__')
    elif hasattr(func, '__name__'):
        func_repr = getattr(func, '__name__')
    else:
        func_repr = repr(func)

    func_repr += _format_args_and_kwargs(args, kwargs)
    if suffix:
        func_repr += suffix
    return func_repr


def _format_callback_source(func, args):
    func_repr = _format_callback(func, args, None)
    source = _get_function_source(func)
    if source:
        func_repr += ' at %s:%s' % source
    return func_repr


class Handle(object):
    def __init__(self, fn, args, loop):
        assert fn is not None

        self._loop = loop
        self._fn = fn
        self._args = args
        self._cancelled = False
        self._repr = None
        if self._loop.get_debug():
            self._source_traceback = traceback.extract_stack(sys._getframe(1))
        else:
            self._source_traceback = None

    def _repr_info(self):
        info = [self.__class__.__name__]
        if self._cancelled:
            info.append('cancelled')
        if self._fn is not None:
            info.append(_format_callback_source(self._fn, self._args))
        if self._source_traceback:
            frame = self._source_traceback[-1]
            info.append('created at %s:%s' % (frame[0], frame[1]))
        return info

    def __repr__(self):
        if self._repr is not None:
            return self._repr
        info = self._repr_info()
        return '<%s>' % ' '.join(info)

    def cancel(self):
        if self._cancelled:
            return False

        self._cancelled = True
        if self._loop.get_debug():
            # Keep a representation in debug mode to to be able to print
            # information about this handle
            self._repr = repr(self)
        self._fn = None
        self._args = None

        return True

    def _run(self):
        try:
            assert not self._cancelled, "Cannot run a cancelled callback"
            self._fn(*self._args)
        except Exception as exc:
            cb = _format_callback_source(self._fn, self._args)
            msg = 'Exception in callback {}'.format(cb)
            context = {
                'message': msg,
                'exception': exc,
                'handle': self,
            }
            if self._source_traceback:
                context['source_traceback'] = self._source_traceback
            self._loop.call_exception_handler(context)
        self = None  # Needed to break cycles when an exception occurs.


class TimerHandle(Handle):
    """
    Handle for callbacks scheduled at a given time
    """

    __slots__ = ['_scheduled', '_when']

    def __init__(self, when, fn, args, loop):
        assert when is not None
        super(TimerHandle, self).__init__(fn, args, loop)
        if self._source_traceback:
            # Delete the one generated from our super
            del self._source_traceback[-1]
        self._when = when
        self._scheduled = False

    def _repr_info(self):
        info = super(TimerHandle, self)._repr_info()
        pos = 2 if self._cancelled else 1
        info.insert(pos, 'when=%s' % self._when)
        return info

    def __hash__(self):
        return hash(self._when)

    def __lt__(self, other):
        return self._when < other._when

    def __le__(self, other):
        if self._when < other._when:
            return True
        return self.__eq__(other)

    def __gt__(self, other):
        return self._when > other._when

    def __ge__(self, other):
        if self._when > other._when:
            return True
        return self.__eq__(other)

    def __eq__(self, other):
        if isinstance(other, TimerHandle):
            return (self._when == other._when and
                    self._fn == other._fn and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal


class AbstractEventLoop(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_future(self):
        """

        :return: A new future
        :rtype: :class:`futures.Future`
        """
        pass

    @abc.abstractmethod
    def run_forever(self):
        pass

    @abc.abstractmethod
    def run_until_complete(self, future):
        pass

    # region Callbacks
    @abc.abstractmethod
    def call_soon(self, fn, *args):
        pass

    @abc.abstractmethod
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

    @abc.abstractmethod
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

    # endregion

    @abc.abstractmethod
    def time(self):
        pass

    @abc.abstractmethod
    def messages(self):
        pass

    # region Objects
    @abc.abstractmethod
    def create(self, object_type, *args, **kwargs):
        """
        Create a task and schedule it to be inserted into the loop.

        :param object_type: The task identifier 
        :param args: (optional) positional arguments to the task
        :param kwargs: (optional) keyword arguments to the task

        :return: The task object
        """
        pass

    @abc.abstractmethod
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

    @abc.abstractmethod
    def get_object_factory(self):
        """
        Get the task factory currently in use.  Returns `None` if the default is
        being used.

        :return: The task factory
        """
        pass

    # endregion

    @abc.abstractmethod
    def close(self):
        """Shutdown the event loop"""
        pass

    # region Error handlers
    @abc.abstractmethod
    def get_exception_handler(self):
        pass

    @abc.abstractmethod
    def set_exception_handler(self, handler):
        pass

    @abc.abstractmethod
    def default_exception_handler(self, context):
        pass

    @abc.abstractmethod
    def call_exception_handler(self, context):
        pass

    # endregion

    # region Debugging
    @abc.abstractmethod
    def get_debug(self):
        pass

    @abc.abstractmethod
    def set_debug(self, enabled):
        pass
        # endregion


class AbstractEventLoopPolicy(with_metaclass(abc.ABCMeta, object)):
    """Abstract policy for accessing the event loop."""

    @abc.abstractmethod
    def get_event_loop(self):
        """Get the event loop for the current context.

        Returns an event loop object implementing the BaseEventLoop interface,
        or raises an exception in case no event loop has been set for the
        current context and the current policy does not specify to create one.

        It should never return None."""
        pass

    @abc.abstractmethod
    def set_event_loop(self, loop):
        """Set the event loop for the current context to loop."""
        pass

    @abc.abstractmethod
    def new_event_loop(self):
        """Create and return a new event loop object according to this
        policy's rules. If there's need to set this loop as the event loop for
        the current context, set_event_loop must be called explicitly."""
        pass


class BaseDefaultEventLoopPolicy(AbstractEventLoopPolicy):
    """Default policy implementation for accessing the event loop.

    In this policy, each thread has its own event loop.  However, we
    only automatically create an event loop by default for the main
    thread; other threads by default have no event loop.

    Other policies may have different rules (e.g. a single global
    event loop, or automatically creating an event loop per thread, or
    using some other notion of context to which an event loop is
    associated).
    """

    _loop_factory = None

    class _Local(threading.local):
        _loop = None
        _set_called = False

    def __init__(self):
        self._local = self._Local()

    def get_event_loop(self):
        """Get the event loop.

        This may be None (in which case RuntimeError is raised) or an instance of EventLoop.
        """
        if (self._local._loop is None and
                not self._local._set_called and
                isinstance(threading.current_thread(), threading._MainThread)):
            self.set_event_loop(self.new_event_loop())
        if self._local._loop is None:
            raise RuntimeError('There is no current event loop in thread %r.'
                               % threading.current_thread().name)
        return self._local._loop

    def set_event_loop(self, loop):
        """Set the event loop."""
        self._local._set_called = True
        assert loop is None or isinstance(loop, AbstractEventLoop)
        self._local._loop = loop

    def new_event_loop(self):
        """Create a new event loop.

        You must call set_event_loop() to make this the current event
        loop.
        """
        return self._loop_factory()


# Event loop policy.  The policy itself is always global, even if the
# policy's rules say that there is an event loop per thread (or other
# notion of context).  The default policy is installed by the first
# call to get_event_loop_policy().
_event_loop_policy = None

# Lock for protecting the on-the-fly creation of the event loop policy.
_lock = threading.Lock()


# A TLS for the running event loop, used by _get_running_loop.
class _RunningLoop(threading.local):
    _loop = []
    _pid = None


_running_loop = _RunningLoop()


def _get_running_loop():
    """Return the running event loop or None.

    This is a low-level function intended to be used by event loops.
    This function is thread-specific.
    """
    if _running_loop._pid == os.getpid():
        if _running_loop._loop:
            return _running_loop._loop[-1]
        else:
            return None


def _push_running_loop(loop):
    """Push a loop onto the running loop stack.

    This is a low-level function intended to be used by event loops.
    This function is thread-specific.
    """
    _running_loop._pid = os.getpid()
    _running_loop._loop.append(loop)


def _pop_running_loop():
    """Pop a loop from the running loop stack.
    Raises exception is there are not loops on the stack.
    :return: The poppsed loop.
    """
    return _running_loop._loop.pop()


def _init_event_loop_policy():
    global _event_loop_policy
    with _lock:
        if _event_loop_policy is None:  # pragma: no branch
            from . import DefaultEventLoopPolicy
            _event_loop_policy = DefaultEventLoopPolicy()


def get_event_loop_policy():
    """Get the current event loop policy."""
    if _event_loop_policy is None:
        _init_event_loop_policy()
    return _event_loop_policy


def set_event_loop_policy(policy):
    """Set the current event loop policy.

    If policy is None, the default policy is restored."""
    global _event_loop_policy
    assert policy is None or isinstance(policy, AbstractEventLoopPolicy)
    _event_loop_policy = policy


def get_event_loop():
    """Return an asyncio event loop.

    When called from a coroutine or a callback (e.g. scheduled with call_soon
    or similar API), this function will always return the running event loop.

    If there is no running event loop set, the function will return
    the result of `get_event_loop_policy().get_event_loop()` call.
    """
    current_loop = _get_running_loop()
    if current_loop is not None:
        return current_loop
    return get_event_loop_policy().get_event_loop()


def set_event_loop(loop):
    """Equivalent to calling get_event_loop_policy().set_event_loop(loop)."""
    get_event_loop_policy().set_event_loop(loop)


def new_event_loop():
    """Equivalent to calling get_event_loop_policy().new_event_loop()."""
    return get_event_loop_policy().new_event_loop()
