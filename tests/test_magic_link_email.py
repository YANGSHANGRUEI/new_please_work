import unittest

from utils.magic_link_email import is_valid_ntu_student_email


class NtuStudentEmailValidatorTests(unittest.TestCase):
    def test_accepts_valid_pattern(self):
        self.assertTrue(is_valid_ntu_student_email("b12a01123@ntu.edu.tw"))
        self.assertTrue(is_valid_ntu_student_email("B99A01399@ntu.edu.tw"))

    def test_rejects_non_ntu_domain(self):
        self.assertFalse(is_valid_ntu_student_email("b12a01123@gmail.com"))

    def test_rejects_invalid_seventh_digit(self):
        self.assertFalse(is_valid_ntu_student_email("b12a01423@ntu.edu.tw"))

    def test_rejects_zero_in_x_positions(self):
        self.assertFalse(is_valid_ntu_student_email("b02a01123@ntu.edu.tw"))
        self.assertFalse(is_valid_ntu_student_email("b12a01103@ntu.edu.tw"))


if __name__ == "__main__":
    unittest.main()