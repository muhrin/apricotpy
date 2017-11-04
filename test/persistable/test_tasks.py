import apricotpy
import apricotpy.persistable as persistable
from . import utils


class PersistableFive(persistable.Task):
    def execute(self):
        return 5


class PersistableTask(persistable.Task):
    def execute(self):
        return apricotpy.Await(PersistableFive().play(), self.finish)

    def finish(self, value):
        return value


class TaskWithContinue(persistable.Task):
    def execute(self):
        return apricotpy.Continue(self.finish)

    def finish(self):
        return 5


class TestPersistableTask(utils.TestCaseWithLoop):
    def test_continue(self):
        task = TaskWithContinue().play()

        saved_state = persistable.Bundle(task)

        loop2 = persistable.BaseEventLoop()
        task2 = saved_state.unbundle(loop2)

        # Finish
        self.assertEqual(~task, 5)
        self.assertEqual(~task2, 5)

        # Check that there is no problem putting it back into original loop
        task = saved_state.unbundle(self.loop)
        result = ~task

        self.assertEqual(result, 5)

    def test_await(self):
        # Tick 0
        task = PersistableTask().play()
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

        # Tick 2
        task = saved_state.unbundle(self.loop)
        self.assertIsNotNone(task.awaiting())
        self.loop.run_until_complete(task.awaiting())

        saved_state = persistable.Bundle(task)

        # Finish
        result = self.loop.run_until_complete(task)
        self.assertEqual(result, 5)
