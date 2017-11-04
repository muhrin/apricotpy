import apricotpy
import unittest
from . import utils


class TestStackDepth(apricotpy.Task):
    def execute(self):
        assert len(apricotpy.events._running_loop._loop) == 2


class LoopStackTester(apricotpy.Task):
    def execute(self):
        subloop = apricotpy.new_event_loop()
        test = subloop.create(TestStackDepth).play()
        subloop.run_until_complete(test)


class TestDefaultLoop(unittest.TestCase):
    def setUp(self):
        super(TestDefaultLoop, self).setUp()
        apricotpy.set_event_loop(apricotpy.get_event_loop_policy().new_event_loop())

    def test_default(self):
        self.assertIsNotNone(apricotpy.get_event_loop())
        self.assertIsNotNone(apricotpy.get_event_loop_policy())

    def test_loop_stack(self):
        loop = apricotpy.get_event_loop()
        tester = loop.create(LoopStackTester).play()
        loop.run_until_complete(tester)
