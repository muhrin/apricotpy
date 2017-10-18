from . import utils
import apricotpy.persistable as persistable


class TestObjectProxy(utils.TestCaseWithLoop):
    def test_basics(self):
        obj = utils.SimpleObject()
        proxy = persistable.ObjectProxy(obj)

        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())
