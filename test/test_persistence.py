import unittest

import apricotpy.persistable.awaitable
from apricotpy import persistable
import apricotpy


class PersistableValue(persistable.LoopObject):
    @staticmethod
    def create(value):
        return PersistableValue(value)

    def __init__(self, value):
        super(PersistableValue, self).__init__()
        self.value = value

    def save_instance_state(self, out_state):
        super(PersistableValue, self).save_instance_state(out_state)
        out_state['value'] = self.value

    def load_instance_state(self, saved_state):
        super(PersistableValue, self).load_instance_state(saved_state)
        self.value = saved_state['value']


class PersistableFive(persistable.Task):
    def execute(self):
        return 5


class TestCaseWithPersistenceLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithPersistenceLoop, self).setUp()
        self.loop = persistable.BaseEventLoop()

    def tearDown(self):
        super(TestCaseWithPersistenceLoop, self).tearDown()
        self.loop.close()
        self.loop = None


class Obj(persistable.ContextMixin, persistable.LoopObject):
    pass


class TestContextMixin(TestCaseWithPersistenceLoop):
    def test_non_persistable(self):
        """
        Try to use the mixin not with a persistable.
        """
        self.assertRaises(AssertionError, persistable.ContextMixin)

    def test_simple(self):
        # Create object with context
        loop_obj = ~self.loop.create_inserted(Obj)

        # Populate the context
        loop_obj.ctx.a = 5
        loop_obj.ctx.b = ('a', 'b')

        # Persist the object in a bundle
        saved_state = persistable.Bundle(loop_obj)

        # Have to remove the original (because UUIDs are same)
        ~self.loop.remove(loop_obj)

        # Load the object from the saved state and compare contexts
        loaded_loop_obj = saved_state.unbundle(self.loop)
        self.assertEqual(loop_obj.ctx, loaded_loop_obj.ctx)

    def test_simple_save_load(self):
        obj = ~self.loop.create_inserted(persistable.LoopObject)
        uuid = obj.uuid

        saved_state = persistable.Bundle(obj)
        ~self.loop.remove(obj)

        obj = saved_state.unbundle(self.loop)
        self.assertEqual(uuid, obj.uuid)

    def test_save_load(self):
        value = 'persist *this*'
        string = ~self.loop.create_inserted(PersistableValue, value)
        self.assertEqual(string.value, value)

        saved_state = persistable.Bundle(string)

        # Have to remove before re-creating
        ~self.loop.remove(string)

        string = saved_state.unbundle(self.loop)
        self.assertEqual(string.value, value)


class PersistableAwaitableFive(apricotpy.persistable.awaitable.AwaitableLoopObject):
    def on_loop_inserted(self, loop):
        super(PersistableAwaitableFive, self).on_loop_inserted(loop)
        if not self.done():
            self.loop().call_soon(self.set_result, 5)


class TestPersistableAwaitable(TestCaseWithPersistenceLoop):
    def test_simple(self):
        persistable_awaitable = ~self.loop.create_inserted(PersistableAwaitableFive)

        saved_state = persistable.Bundle(persistable_awaitable)

        self.loop.run_until_complete(persistable_awaitable)

        persistable_awaitable = saved_state.unbundle(self.loop)
        self.loop.run_until_complete(persistable_awaitable)


