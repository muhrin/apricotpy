import logging

import apricotpy
from apricotpy import objects
from . import core

__all__ = ['LoopObject']

_LOGGER = logging.getLogger(__name__)


class PersistableLoopObjectMixin(core.Persistable):
    """
    A mixin that makes a :class:`objects.LoopObject` :class:`Persistable`.

    Because this is a mixin in can be inserted an any point in the inheritance hierarchy.
    """
    IN_LOOP = 'IN_LOOP'
    LOOP_CALLBACK = 'LOOP_CALLBACK'
    UUID = 'UUID'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, objects.LoopObject), "Has to be used with a LoopObject"
        super(PersistableLoopObjectMixin, self).__init__(*args, **kwargs)

    def save_instance_state(self, out_state):
        super(PersistableLoopObjectMixin, self).save_instance_state(out_state)
        out_state[self.UUID] = self.uuid
        out_state[self.IN_LOOP] = self.in_loop()
        out_state[self.LOOP_CALLBACK] = self._loop_callback

    def load_instance_state(self, saved_state, loop):
        super(PersistableLoopObjectMixin, self).load_instance_state(saved_state, loop)

        self._uuid = saved_state[self.UUID]
        if saved_state[self.IN_LOOP]:
            assert loop is not None, "Cannot create this loop object without an event loop"
            self._loop = loop
            self._loop._insert_object(self)
        else:
            self._loop = None
        self._loop_callback = saved_state[self.LOOP_CALLBACK]


class LoopObject(apricotpy.LoopObject, PersistableLoopObjectMixin):
    """
    A convenience to get a LoopObject that is Persistable.  
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass
