import json
import unittest
from unittest import mock
from person_reference import PersonReference


class PersonReferenceTest(unittest.TestCase):

    def setUp(self):
        self.person_reference = PersonReference(apikey='12345', environment='testing')

        self.fake_schools = {
            "count": 3,
            "results": [
                {
                    "code": "01",
                    "description": "Fake College 1",
                    "effectiveStatus": "A",
                    "effectiveDate": "1996-01-01T00:00:00Z"
                },
                {
                    "code": "02",
                    "description": "Fake College 2",
                    "effectiveStatus": "I",
                    "effectiveDate": "1990-02-01T00:00:00Z"
                },
                {
                    "code": "03",
                    "description": "Fake College 3",
                    "effectiveStatus": "A",
                    "effectiveDate": "1991-06-01T00:00:00Z"
                }
            ]
        }

    @mock.patch('requests.get')
    def test_get_health_check(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response
        expected_url = f"https://{self.person_reference.host}/ats/person/reference/v1/health"

        # Call the healthCheck method
        result = self.person_reference.healthCheck()

        # Assert the response
        self.assertEqual(result, "OK")
        mock_get.assert_called_once_with(expected_url, headers=self.person_reference.headers)


    @mock.patch('requests.get')
    def test_get_schools(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.fake_schools
        mock_response.text = json.dumps(self.fake_schools)
        mock_get.return_value = mock_response
        expected_url = f"https://{self.person_reference.host}/ats/person/reference/v1/studentSchool"

        # Call the getSchools method
        result = self.person_reference.getSchools()

        # Assert the response
        self.assertEqual(result, self.fake_schools)
        mock_get.assert_called_once_with(expected_url, headers=self.person_reference.headers)

    



if __name__ == '__main__':
    unittest.main()