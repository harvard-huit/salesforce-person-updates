import unittest
from unittest import mock
from pds import People


class PeoplesTest(unittest.TestCase):

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
        results = People(apikey='fakekey', query={}).results
        self.assertEqual(len(results), 2)


    @mock.patch('pds.People.search', side_effect=mocked_get_people)
    def test_hash(self, mock_get):
        people = People(apikey='fakekey', query={}).people
        self.assertEqual(people[0]['personKey'], 1)
        self.assertEqual(people[1]['personKey'], 2)


if __name__ == '__main__':
    unittest.main()