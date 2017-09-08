from . import utils
import apricotpy.persistable as persistable


class TestObjectProxy(utils.TestCaseWithLoop):
    def test_basics(self):
        obj = utils.SimpleObject()
        proxy = persistable.ObjectProxy(obj)

        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())

        # Insert obj into loop
        self.loop.run_until_complete(obj.insert_into(self.loop))
        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())

        # Remove
        self.loop.run_until_complete(obj.remove())
        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())

        # Now insert the proxy
        self.loop.run_until_complete(proxy.insert_into(self.loop))
        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())

        # and remove
        self.loop.run_until_complete(proxy.remove())
        self.assertEqual(obj.loop(), proxy.loop())
        self.assertEqual(obj.in_loop(), proxy.in_loop())
