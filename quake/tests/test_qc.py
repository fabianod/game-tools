import unittest

from quake.tests import basecase
from quake import qc

class TestBasic(basecase.TestCase):
    def test_variable_declaration(self):
        prog = """self.test = {
t = 0;       
};"""

        ast = qc.parse(prog)
        print(ast)

if __name__ == '__main__':
    unittest.main()
