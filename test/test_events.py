import apricotpy
import unittest


class StackDepthTester(apricotpy.Task):
    def execute(self):
        assert len(apricotpy.events._running_loop._loop) == 2


class LoopStackTester(apricotpy.Task):
    def execute(self):
        subloop = apricotpy.new_event_loop()
        test = subloop.create(StackDepthTester)
        subloop.run_until_complete(test)


class TestDefaultLoop(unittest.TestCase):
    def setUp(self):
        super(TestDefaultLoop, self).setUp()
        apricotpy.set_event_loop(apricotpy.get_event_loop_policy().new_event_loop())

    def test_default(self):
        self.assertIsNotNone(apricotpy.get_event_loop())
        self.assertIsNotNone(apricotpy.get_event_loop_policy())

    def test_loop_stack(self):
        tester = apricotpy.get_event_loop().create(LoopStackTester)
        apricotpy.get_event_loop().run_until_complete(tester)
