import unittest
from pyrocast_cfbt.native import native_float

class NativeExponentTests(unittest.TestCase):
    def test_three_digit_fortran_exponent(self):
        self.assertEqual(native_float('  8.4980222229621647-100'),8.4980222229621647e-100)
        self.assertEqual(native_float('-.120+101'),-.120e101)
        self.assertEqual(native_float('1.0D-12'),1e-12)
        self.assertEqual(native_float('3.1E-10'),3.1e-10)

    def test_not_a_general_expression_or_truncated_number_parser(self):
        for text in ['1.2-3','8.4--100','1-100','****','text-100']:
            with self.assertRaises(ValueError):native_float(text)
