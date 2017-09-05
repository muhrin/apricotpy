import apricotpy
from . import events
from . import objects

__all__ = ['AwaitableLoopObject']


class MakeAwaitableMixinPersistable(object):
    """
    Take a :class:`apricotpy.AwaitableMixin` and make it :class:`core.Persistable` 
    """

    STATE = 'STATE'
    RESULT = 'RESULT'
    EXCEPTION = 'EXCEPTION'
    CALLBACKS = 'CALLBACKS'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, apricotpy.AwaitableMixin), "Has to be used with an AwaitableMixin"
        super(MakeAwaitableMixinPersistable, self).__init__(*args, **kwargs)

    def save_instance_state(self, out_state):
        super(MakeAwaitableMixinPersistable, self).save_instance_state(out_state)

        out_state[self.STATE] = self._future._state
        out_state[self.RESULT] = self._future._result
        out_state[self.EXCEPTION] = self._future._exception
        out_state[self.CALLBACKS] = tuple(self._callbacks)

    def load_instance_state(self, saved_state, loop):
        super(MakeAwaitableMixinPersistable, self).load_instance_state(saved_state, loop)

        fut = apricotpy.futures._FutureBase()
        fut._state = saved_state[self.STATE]
        fut._result = saved_state[self.RESULT]
        fut._exception = saved_state[self.EXCEPTION]
        self._future = fut

        self._callbacks = list(saved_state[self.CALLBACKS])


class AwaitableMixin(MakeAwaitableMixinPersistable, apricotpy.AwaitableMixin):
    pass


class AwaitableLoopObject(
    AwaitableMixin,
    objects.LoopObject):  # Start as a persistable LoopObject
    """
    A convenience class that gives a LoopObject that is both Persistable and
    Awaitable.
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass
