import unittest
from apricotpy import persistence
import apricotpy


class PersistableValue(apricotpy.PersistableLoopObject):
    @staticmethod
    def create(loop, value):
        return PersistableValue(loop, value)

    def __init__(self, loop, value):
        super(PersistableValue, self).__init__(loop)
        self.value = value

    def save_instance_state(self, out_state):
        super(PersistableValue, self).save_instance_state(out_state)
        out_state['value'] = self.value

    def load_instance_state(self, loop, saved_state, *args):
        super(PersistableValue, self).load_instance_state(loop, saved_state, *args)
        self.value = saved_state['value']


class PersistableFive(apricotpy.PersistableTask):
    def execute(self):
        return 5


class TestCaseWithPersistenceLoop(unittest.TestCase):
    def setUp(self):
        super(TestCaseWithPersistenceLoop, self).setUp()
        self.loop = apricotpy.BaseEventLoop()
        self.loop.set_object_factory(apricotpy.persistable_object_factory)

    def tearDown(self):
        super(TestCaseWithPersistenceLoop, self).tearDown()
        self.loop.close()
        self.loop = None


class TestContextMixin(TestCaseWithPersistenceLoop):
    def test_non_persistable(self):
        """
        Try to use the mixin not with a persistable.
        """
        self.assertRaises(AssertionError, persistence.ContextMixin)

    def test_simple(self):
        class Obj(apricotpy.ContextMixin, apricotpy.PersistableLoopObject):
            pass

        # Create object with context
        loop_obj = self.loop.create(Obj)

        # Populate the context
        loop_obj.ctx.a = 5
        loop_obj.ctx.b = ('a', 'b')

        # Persist the object in a bundle
        saved_state = persistence.Bundle()
        loop_obj.save_instance_state(saved_state)

        # Have to remove the original (because UUIDs are same)
        self.loop.remove(loop_obj)

        # Load the object from the saved state and compare contexts
        loaded_loop_obj = self.loop.create(Obj, saved_state)
        self.assertEqual(loop_obj.ctx, loaded_loop_obj.ctx)

    def test_simple_save_load(self):
        obj = self.loop.create(apricotpy.PersistableLoopObject)
        uuid = obj.uuid

        saved_state = apricotpy.Bundle()
        obj.save_instance_state(saved_state)
        self.loop.remove(obj)

        obj = self.loop.create(apricotpy.PersistableLoopObject, saved_state)
        self.assertEqual(uuid, obj.uuid)

    def test_save_load(self):
        value = 'persist *this*'
        string = self.loop.create(PersistableValue, value)
        self.assertEqual(string.value, value)

        saved_state = apricotpy.Bundle()
        string.save_instance_state(saved_state)
        # Have to remove before re-creating
        self.loop.remove(string)

        string = self.loop.create(PersistableValue, saved_state)
        self.assertEqual(string.value, value)


class PersistableAwaitableFive(apricotpy.PersistableAwaitableLoopObject):
    def on_loop_inserted(self, loop):
        super(PersistableAwaitableFive, self).on_loop_inserted(loop)
        if not self.done():
            self.loop().call_soon(self.set_result, 5)


class TestPersistableAwaitable(TestCaseWithPersistenceLoop):
    def test_simple(self):
        persistable_awaitable = ~self.loop.create_inserted(PersistableAwaitableFive)

        saved_state = apricotpy.Bundle()
        persistable_awaitable.save_instance_state(saved_state)

        self.loop.run_until_complete(persistable_awaitable)

        persistable_awaitable = self.loop.create(PersistableAwaitableFive, saved_state)
        self.loop.run_until_complete(persistable_awaitable)


class TestPersistableTask(TestCaseWithPersistenceLoop):
    def test_continue(self):
        class PersistableTask(apricotpy.PersistableTask):
            def execute(self):
                return apricotpy.Continue(self.finish)

            def finish(self):
                return 5

        task = ~self.loop.create_inserted(PersistableTask)

        saved_state = apricotpy.Bundle()
        task.save_instance_state(saved_state)

        # Remove
        self.loop.run_until_complete(task)

        task = self.loop.create(PersistableTask, saved_state)
        result = self.loop.run_until_complete(task)

        self.assertEqual(result, 5)

    def test_await(self):
        class PersistableTask(apricotpy.PersistableTask):
            def execute(self):
                return apricotpy.Await(self.loop().create(PersistableFive), self.finish)

            def finish(self, value):
                return value

        # Tick 0
        task = ~self.loop.create_inserted(PersistableTask)

        saved_state = apricotpy.Bundle()
        task.save_instance_state(saved_state)

        # Finish
        result = self.loop.run_until_complete(task)
        self.assertEqual(result, 5)

        # Tick 1
        task = ~self.loop.create_inserted(PersistableTask, saved_state)
        self.loop.tick()  # Awaiting
        awaiting = task.awaiting()
        self.assertIsNotNone(awaiting)

        saved_state = apricotpy.Bundle()
        task.save_instance_state(saved_state)

        # Finish
        result = self.loop.run_until_complete(task)
        self.assertEqual(result, 5)
        self.assertFalse(awaiting.in_loop())

        # Tick 2
        task = ~self.loop.create_inserted(PersistableTask, saved_state)
        self.assertIsNotNone(task.awaiting())
        self.loop.run_until_complete(task.awaiting())

        saved_state = apricotpy.Bundle()
        task.save_instance_state(saved_state)

        # Finish
        result = self.loop.run_until_complete(task)
        self.assertEqual(result, 5)
