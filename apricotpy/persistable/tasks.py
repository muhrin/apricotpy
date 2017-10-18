import abc

from future.utils import with_metaclass

import apricotpy.tasks
from . import awaitable
from . import objects

_NO_RESULT = apricotpy.tasks._NO_RESULT

__all__ = ['Task']


class Task(with_metaclass(
    abc.ABCMeta,
    awaitable.MakeAwaitableMixinPersistable,  # make Awaitable also LoopPersistable
    apricotpy.tasks.TaskMixin,
    objects.LoopObject)):

    AWAITING = 'AWAITING'
    AWAITING_RESULT = 'AWAITING_RESULT'
    CALLBACK_HANDLE = 'CALLBACK_HANDLE'
    NEXT_STEP = 'NEXT_STEP'

    def __init__(self, loop=None):
        super(Task, self).__init__(loop)
        self.__saved_state = None

    def save_instance_state(self, out_state):
        super(Task, self).save_instance_state(out_state)

        out_state[self.NEXT_STEP] = self._next_step
        out_state[self.AWAITING] = self._awaiting
        out_state[self.CALLBACK_HANDLE] = self._callback_handle

        if self._awaiting_result is not _NO_RESULT:
            out_state[self.AWAITING_RESULT] = self._awaiting_result

    def load_instance_state(self, saved_state):
        super(Task, self).load_instance_state(saved_state)

        self._awaiting = saved_state[self.AWAITING]

        self._paused = False
        self._callback_handle = saved_state[self.CALLBACK_HANDLE]

        try:
            self._next_step = saved_state[self.NEXT_STEP]
        except KeyError:
            self._next_step = None

        try:
            self._awaiting_result = saved_state[self.AWAITING_RESULT]
        except KeyError:
            self._awaiting_result = _NO_RESULT
