import apricotpy
import unittest


class TestStackDepth(apricotpy.Task):
    def execute(self):
        assert len(apricotpy.events._running_loop._loop) == 2


class LoopStackTester(apricotpy.Task):
    def execute(self):
        subloop = apricotpy.new_event_loop()
        test = subloop.create(TestStackDepth)
        subloop.run_until_complete(test)


class TestDefaultLoop(unittest.TestCase):
    def test_default(self):
        self.assertIsNotNone(apricotpy.get_event_loop())
        self.assertIsNotNone(apricotpy.get_event_loop_policy())

    def test_loop_stack(self):
        tester = apricotpy.get_event_loop().create(LoopStackTester)
        apricotpy.get_event_loop().run_until_complete(tester)
