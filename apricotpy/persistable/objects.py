import logging

import apricotpy
from apricotpy import objects
from . import core

__all__ = ['LoopObject']

_LOGGER = logging.getLogger(__name__)


class PersistableLoopObjectMixin(core.LoopPersistable):
    """
    A mixin that makes a :class:`objects.LoopObject` :class:`LoopPersistable`.

    Because this is a mixin in can be inserted an any point in the inheritance hierarchy.
    """
    IN_LOOP = 'IN_LOOP'
    CALLBACKS = 'CALLBACKS'
    LOOP_CALLBACK = 'LOOP_CALLBACK'
    UUID = 'UUID'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, objects.LoopObject), "Has to be used with a LoopObject"
        super(PersistableLoopObjectMixin, self).__init__(*args, **kwargs)

        self._callbacks = []

    @property
    def persistable_id(self):
        return self.uuid

    def save_instance_state(self, out_state):
        super(PersistableLoopObjectMixin, self).save_instance_state(out_state)

        out_state[self.UUID] = self.uuid
        out_state[self.CALLBACKS] = tuple(self._callbacks)

    def load_instance_state(self, saved_state):
        super(PersistableLoopObjectMixin, self).load_instance_state(saved_state)

        self._loop = saved_state.loop()
        self._uuid = saved_state[self.UUID]
        self._callbacks = list(saved_state[self.CALLBACKS])

        self._loop._insert_object(self)

    def call_soon(self, fn, *args, **kwargs):
        self.persist_callback(
            self.loop().call_soon(fn, *args, **kwargs)
        )

    def persist_callback(self, handle):
        self._callbacks.append(handle)
        handle.add_done_callback(self._callback_done)

    def _callback_done(self, handle):
        self._callbacks.remove(handle)


class LoopObject(apricotpy.LoopObject, PersistableLoopObjectMixin):
    """
    A convenience to get a LoopObject that is LoopPersistable.  
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass
