from abc import ABCMeta

import apricotpy.tasks
from . import awaitable
from . import core
from . import objects

_NO_RESULT = apricotpy.tasks._NO_RESULT

__all__ = ['Task']


class Task(
    awaitable.MakeAwaitableMixinPersistable,  # make Awaitable also LoopPersistable
    apricotpy.tasks.TaskMixin,
    objects.LoopObject):
    __metaclass__ = ABCMeta

    AWAITING = 'AWAITING'
    AWAITING_RESULT = 'AWAITING_RESULT'
    CALLBACK_HANDLE = 'CALLBACK_HANDLE'
    NEXT_STEP = 'NEXT_STEP'

    def __init__(self):
        super(Task, self).__init__()
        self.__saved_state = None

    def save_instance_state(self, out_state):
        super(Task, self).save_instance_state(out_state)

        self._save_next_step(out_state)
        out_state[self.AWAITING] = self._awaiting
        out_state[self.CALLBACK_HANDLE] = self._callback_handle

        if self._awaiting_result is not _NO_RESULT:
            out_state[self.AWAITING_RESULT] = self._awaiting_result

    def load_instance_state(self, saved_state, loop):
        super(Task, self).load_instance_state(saved_state, loop)

        self._awaiting = saved_state[self.AWAITING]

        self._paused = False
        self._callback_handle = saved_state[self.CALLBACK_HANDLE]

        self._next_step = None
        self._load_next_step(saved_state[self.NEXT_STEP])

        try:
            self._awaiting_result = saved_state[self.AWAITING_RESULT]
        except KeyError:
            self._awaiting_result = _NO_RESULT

    def _save_next_step(self, out_state):
        if self._next_step is None:
            out_state[self.NEXT_STEP] = None
        else:
            out_state[self.NEXT_STEP] = self._next_step.__name__

    def _load_next_step(self, next_step_name):
        if next_step_name is not None:
            try:
                self._set_next_step(getattr(self, next_step_name))
            except AttributeError:
                raise ValueError(
                    "This Task does not have a function with "
                    "the name '{}' as expected from the saved state".
                        format(next_step_name)
                )
        else:
            self._set_next_step(None)
