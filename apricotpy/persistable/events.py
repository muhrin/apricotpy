import inspect
import logging
import apricotpy
import apricotpy.events
from . import core
from . import persistables

_LOGGER = logging.getLogger(__name__)


class _PersistableHandleMixin(core.LoopPersistable):
    FN = 'FN'
    ARGS = 'ARGS'
    CANCELLED = 'CANCELLED'
    REPR = 'REPR'

    def save_instance_state(self, out_state):
        super(_PersistableHandleMixin, self).save_instance_state(out_state)

        out_state[self.FN] = self._fn
        out_state[self.ARGS] = self._args
        out_state[self.CANCELLED] = self._cancelled
        out_state[self.REPR] = self._repr

    def load_instance_state(self, saved_state):
        super(_PersistableHandleMixin, self).load_instance_state(saved_state)

        self._loop = saved_state.loop()
        self._fn = saved_state[self.FN]
        self._args = saved_state[self.ARGS]
        self._cancelled = saved_state[self.CANCELLED]
        self._repr = saved_state[self.REPR]


class Handle(_PersistableHandleMixin, apricotpy.events.Handle):
    WHEN = 'WHEN'
    OWNER = 'OWNER'
    RAN = -1

    def __init__(self, fn, args, loop, owner=None):
        super(Handle, self).__init__(fn, args, loop)
        self._owner = owner
        self._when = None

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
        if isinstance(other, Handle):
            return (self._when == other._when and
                    self._fn == other._fn and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal

    def loop(self):
        return self._loop

    def save_instance_state(self, out_state):
        super(Handle, self).save_instance_state(out_state)
        out_state[self.WHEN] = self._when
        out_state[self.OWNER] = self._owner

    def load_instance_state(self, saved_state):
        super(Handle, self).load_instance_state(saved_state)
        self._when = saved_state[self.WHEN]
        self._owner = saved_state[self.OWNER]

    def _run(self):
        self._when = self.RAN
        super(Handle, self)._run()


class TimerHandle(Handle):
    SCHEDULED = 'SCHEDULED'

    __slots__ = ['_scheduled', '_when']

    def __init__(self, when, fn, args, loop, owner=None):
        assert when is not None
        super(TimerHandle, self).__init__(fn, args, loop, owner)
        if self._source_traceback:
            # Delete the one generated from our super
            del self._source_traceback[-1]
        self._scheduled = False

    def _repr_info(self):
        info = super(TimerHandle, self)._repr_info()
        pos = 2 if self._cancelled else 1
        info.insert(pos, 'when=%s' % self._when)
        return info

    def __eq__(self, other):
        if isinstance(other, TimerHandle):
            return (self._when == other._when and
                    self._fn == other._fn and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented

    def save_instance_state(self, out_state):
        super(TimerHandle, self).save_instance_state(out_state)
        out_state[self.SCHEDULED] = self._scheduled

    def load_instance_state(self, saved_state):
        super(TimerHandle, self).load_instance_state(saved_state)
        self._scheduled = saved_state[self.SCHEDULED]


def _get_loop_persistable_from_fn(fn):
    """
    If the function passed is actually a method or a
    :class:`persistables.Function` and the owning object is a LoopPersistable
    the object will be returned.  Otherwise None.

    :param fn: The function
    :return: The loop object, or None
    """
    if isinstance(fn, persistables.Function):
        fn = fn._fn
    if inspect.ismethod(fn) and isinstance(fn.__self__, core.LoopPersistable):
        return fn.__self__
