import unittest
from unittest import mock
from departments import Departments


class DepartmentsTest(unittest.TestCase):

    def mocked_get_departments(*args, **kwargs):
        fake_departments = [
            {
                'hrDeptId': 1,
                'something': "something for 1"
            },
            {
                'hrDeptId': 2,
                'something': "something for 2"
            }
        ]
        return fake_departments

    @mock.patch('departments.Departments.getDepartments', side_effect=mocked_get_departments)
    def test_mock(self, mock_get):
        results = Departments(apikey='fakekey').results
        self.assertEqual(len(results), 2)


    @mock.patch('departments.Departments.getDepartments', side_effect=mocked_get_departments)
    def test_hash(self, mock_get):
        departments = Departments(apikey='fakekey').department_hash
        self.assertEqual(departments[1]['hrDeptId'], 1)
        self.assertEqual(departments[2]['hrDeptId'], 2)


if __name__ == '__main__':
    unittest.main()