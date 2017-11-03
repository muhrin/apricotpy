import logging
import apricotpy
from apricotpy import objects
from . import core

__all__ = ['LoopObject', 'PersistableLoopObjectMixin']

_LOGGER = logging.getLogger(__name__)


class PersistableLoopObjectMixin(core.LoopPersistable):
    """
    A mixin that makes a :class:`objects.LoopObject` :class:`LoopPersistable`.

    Because this is a mixin in can be inserted an any point in the inheritance hierarchy.
    """
    IN_LOOP = 'IN_LOOP'
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

    def load_instance_state(self, saved_state):
        super(PersistableLoopObjectMixin, self).load_instance_state(saved_state)

        self._loop = saved_state.loop()
        self._uuid = saved_state[self.UUID]


class LoopObject(apricotpy.LoopObject, PersistableLoopObjectMixin):
    """
    A convenience to get a LoopObject that is LoopPersistable.  
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass
