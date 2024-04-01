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
    def test_get_results_text(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response

        # Call the getResultsText method
        result = self.person_reference.getResultsText(self.person_reference.health_url)

        # Assert the response
        self.assertEqual(result, "OK")
        mock_get.assert_called_once_with(self.person_reference.health_url, headers=self.person_reference.headers)

    @mock.patch('requests.get')
    def test_get_results_text_failure(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        # Call the getResultsText method
        with self.assertRaises(Exception) as e:
            self.person_reference.getResultsText(self.person_reference.health_url)

        # Assert the response
        self.assertEqual(str(e.exception), "Error: failure with response from Reference API")

    @mock.patch('requests.get')
    def test_get_results_json(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.fake_schools
        mock_get.return_value = mock_response

        # Call the getResultsJson method
        result = self.person_reference.getResultsJson(self.person_reference.schools_url)

        # Assert the response
        self.assertEqual(result, self.fake_schools['results'])
        mock_get.assert_called_once_with(self.person_reference.schools_url, headers=self.person_reference.headers)

    @mock.patch('requests.get')
    def test_get_results_json_failure(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        # Call the getResultsJson method
        with self.assertRaises(Exception) as e:
            self.person_reference.getResultsJson(self.person_reference.schools_url)

        # Assert the response
        self.assertEqual(str(e.exception), "Error: failure with response from Reference API")

    @mock.patch('person_reference.PersonReference.getResultsJson')
    def test_get_schools(self, mock_get):

        # Call the getSchools method
        result = self.person_reference.getSchools()

        # Assert the getResultsJson method was called
        mock_get.assert_called_once_with(self.person_reference.schools_url)
    




if __name__ == '__main__':
    unittest.main()