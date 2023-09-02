import unittest
from unittest import mock
import pds


class PeoplesTest(unittest.TestCase):

    def setUp(self):
        self.pds = pds.People(apikey='fake_key')

    def mocked_get_people(*args, **kwargs):
        fake_people = {
            'count': 2,
            'total_count': 2,
            'results': [
                {
                    'personKey': 1,
                    'something': "something for 1"
                },
                {
                    'personKey': 2,
                    'something': "something for 2"
                }
            ]
        }
        return fake_people
    
    @mock.patch('pds.People.search', side_effect=mocked_get_people)
    def test_mock(self, mock_get):
        results = self.pds.get_people(query={})
        self.assertEqual(len(results), 2)


    @mock.patch('pds.People.search', side_effect=mocked_get_people)
    def test_hash(self, mock_get):
        people = self.pds.get_people(query={})
        self.assertEqual(people[0]['personKey'], 1)
        self.assertEqual(people[1]['personKey'], 2)


if __name__ == '__main__':
    unittest.main()