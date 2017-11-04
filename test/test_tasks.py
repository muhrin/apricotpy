import apricotpy

from . import utils


class Five(apricotpy.Task):
    def execute(self):
        return 5


class EventuallyFive(apricotpy.Task):
    def execute(self):
        return apricotpy.Continue(self.finish)

    def finish(self):
        return 5


class AwaitFive(apricotpy.Task):
    def execute(self):
        return apricotpy.Await(Five().play(), self.finish)

    def finish(self, value):
        return value


class TestTask(utils.TestCaseWithLoop):
    def test_simple(self):
        five = Five().play()
        result = self.loop.run_until_complete(five)

        self.assertEqual(result, 5)

    def test_continue(self):
        five = EventuallyFive().play()
        result = self.loop.run_until_complete(five)

        self.assertEqual(result, 5)

    def test_await(self):
        await_five = AwaitFive().play()
        result = self.loop.run_until_complete(await_five)
        self.assertEqual(result, 5)
