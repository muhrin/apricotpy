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
        return apricotpy.Await(self.loop().create(Five), self.finish)

    def finish(self, value):
        return value


class TestTask(utils.TestCaseWithLoop):
    def test_simple(self):
        five = self.loop.create(Five)
        result = self.loop.run_until_complete(five)

        self.assertEqual(result, 5)

    def test_continue(self):
        five = self.loop.create(EventuallyFive)
        result = self.loop.run_until_complete(five)

        self.assertEqual(result, 5)

    def test_await(self):
        await_five = self.loop.create(AwaitFive)
        result = self.loop.run_until_complete(await_five)

        self.assertEqual(result, 5)
