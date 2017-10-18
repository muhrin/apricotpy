import apricotpy
from . import core

__all__ = ['gather']


class Future(apricotpy.Future, core.LoopPersistable):
    STATE = 'STATE'
    RESULT = 'RESULT'
    EXCEPTION = 'EXCEPTION'
    DONE_CALLBACKS = 'DONE_CALLBACKS'

    def loop(self):
        return self._loop

    def save_instance_state(self, out_state):
        super(Future, self).save_instance_state(out_state)

        out_state[self.STATE] = self._state
        out_state[self.RESULT] = self._result
        out_state[self.EXCEPTION] = self._exception
        out_state[self.DONE_CALLBACKS] = tuple(self._callbacks)

    def load_instance_state(self, saved_state):
        super(Future, self).load_instance_state(saved_state)

        self._loop = saved_state.loop()
        self._state = saved_state[self.STATE]
        self._result = saved_state[self.RESULT]
        self._exception = saved_state[self.EXCEPTION]
        self._callbacks = list(saved_state[self.DONE_CALLBACKS])


class _GatheringFuture(apricotpy.futures._gathering_future_template(Future)):
    CHILDREN = 'CHILDREN'
    N_DONE = 'N_DONE'
    
    def save_instance_state(self, out_state):
        super(_GatheringFuture, self).save_instance_state(out_state)

        out_state[self.CHILDREN] = self._children
        out_state[self.N_DONE] = self._n_done

    def load_instanece_state(self, saved_state):
        super(_GatheringFuture, self).load_instanece_state(saved_state)

        self._children = saved_state[self.CHILDREN]
        self._n_done = saved_state[self.N_DONE]


def gather(awaitables, loop):
    """
    Gather multiple awaitables into a single :class:`Awaitable`

    :param awaitables: The awaitables to gather
    :param loop: The event loop
    :return: An awaitable representing all the awaitables
    :rtype: :class:`Awaitable`
    """
    if isinstance(awaitables, apricotpy.Awaitable):
        return awaitables

    return _GatheringFuture(awaitables, loop)
