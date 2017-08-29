import apricotpy
import apricotpy.persistable as persistable
from . import utils


class PersistableFive(persistable.Task):
    def execute(self):
        return 5


class PersistableTask(persistable.Task):
    def execute(self):
        return apricotpy.Await(self.loop().create(PersistableFive), self.finish)

    def finish(self, value):
        return value


class TaskWithContinue(persistable.Task):
    def execute(self):
        return apricotpy.Continue(self.finish)

    def finish(self):
        return 5


class TestPersistableTask(utils.TestCaseWithLoop):
    def test_continue(self):
        task = ~self.loop.create_inserted(TaskWithContinue)

        saved_state = persistable.Bundle(task)

        loop2 = persistable.BaseEventLoop()
        saved_state.unbundle(loop2)

        # Finish
        ~task

        task = saved_state.unbundle(self.loop)
        result = ~task

        self.assertEqual(result, 5)

    def test_await(self):
        # Tick 0
        task = ~self.loop.create_inserted(PersistableTask)

        uuid = task.uuid

        saved_state = persistable.Bundle(task)

        # Finish
        result = ~task
        self.assertEqual(result, 5)

        # Tick 1
        task = saved_state.unbundle(self.loop)

        self.loop.tick()  # Awaiting
        awaiting = task.awaiting()
        self.assertIsNotNone(awaiting)

        saved_state = persistable.Bundle(task)

        # Finish
        result = ~task
        self.assertEqual(result, 5)
        self.assertFalse(awaiting.in_loop())

        # Tick 2
        task = saved_state.unbundle(self.loop)
        self.assertIsNotNone(task.awaiting())
        self.loop.run_until_complete(task.awaiting())

        saved_state = persistable.Bundle(task)

        # Finish
        result = self.loop.run_until_complete(task)
        self.assertEqual(result, 5)
