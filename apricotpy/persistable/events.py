import apricotpy.events
import logging
from . import core

_LOGGER = logging.getLogger(__name__)


class _PersistableHandleMixin(core.Persistable):
    FN = 'FN'
    ARGS = 'ARGS'
    CANCELLED = 'CANCELLED'

    def save_instance_state(self, out_state):
        super(_PersistableHandleMixin, self).save_instance_state(out_state)

        out_state[self.FN] = self._fn
        out_state[self.ARGS] = self._args
        out_state[self.CANCELLED] = self._cancelled

    def load_instance_state(self, saved_state, loop):
        super(_PersistableHandleMixin, self).load_instance_state(saved_state, loop)

        self._loop = loop
        self._fn = saved_state[self.FN]
        self._args = saved_state[self.ARGS]
        self._cancelled = saved_state[self.CANCELLED]


class Handle(_PersistableHandleMixin, apricotpy.events.Handle):
    WHEN_READY = 'WHEN_READY'
    RAN = -1

    def __init__(self, fn, args, loop):
        # fn = ensure_persistable_callback(fn)
        super(Handle, self).__init__(fn, args, loop)
        self._when_ready = None

    def save_instance_state(self, out_state):
        super(Handle, self).save_instance_state(out_state)
        out_state[self.WHEN_READY] = self._when_ready

    def load_instance_state(self, saved_state, loop):
        super(Handle, self).load_instance_state(saved_state, loop)
        self._when_ready = saved_state[self.WHEN_READY]
        if self._when_ready != self.RAN:
            self._loop._insert_callback(self)

    def __hash__(self):
        return hash(self._when_ready)

    def __lt__(self, other):
        return self._when_ready < other._when_ready

    def __le__(self, other):
        if self._when_ready < other._when_ready:
            return True
        return self.__eq__(other)

    def __gt__(self, other):
        return self._when_ready > other._when_ready

    def __ge__(self, other):
        if self._when_ready > other._when_ready:
            return True
        return self.__eq__(other)

    def __eq__(self, other):
        if isinstance(other, Handle):
            return (self._when_ready == other._when_ready and
                    self._fn == other._fn and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal

    def loop(self):
        return self._loop

    def _run(self):
        super(Handle, self)._run()
        self._when_ready = self.RAN


class TimerHandle(Handle):
    WHEN = 'WHEN'
    SCHEDULED = 'SCHEDULED'

    __slots__ = ['_scheduled', '_when']

    def __init__(self, when, fn, args, loop):
        assert when is not None
        super(TimerHandle, self).__init__(fn, args, loop)
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

    def save_instance_state(self, out_state):
        super(TimerHandle, self).save_instance_state(out_state)
        out_state[self.WHEN] = self._when
        out_state[self.SCHEDULED] = self._scheduled

    def load_instance_state(self, saved_state, loop):
        super(TimerHandle, self).load_instance_state(saved_state, loop)
        self._when = saved_state[self.WHEN]
        self._scheduled = saved_state[self.SCHEDULED]
