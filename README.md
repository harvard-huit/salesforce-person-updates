# Salesforce Person Updates

The salesforce-person-updates project pushes person data from the PDS to the specified Salesforce instance. 


## Development Notes

In order to run this locally, you'll need: 

### Apikey to the PDS and or HR Departments API

TODO: link to the PDS request form

### Test Salesforce instance

A sandbox or development or scratch Salesforce instance and an admin-level integration user. 

### .env file

A `.env` file is the best way to work on this locally. Otherwise you'll need to have the data in an accessible dynamo table + secrets manager.  

A local file would look like:
```
LOCAL="True"
STACK="developer"
PDS_APIKEY="<PDS Apikey>"
DEPT_APIKEY="<Departments API Apikey>"

DEBUG="False"

SF_USERNAME="<your salesforce username>"
SF_PASSWORD="<your salesforce password>"
SF_DOMAIN="test"
# SF_CLIENT_KEY="<your client key>"
# SF_CLIENT_SECRET="<your client secret>"
SF_SECURITY_TOKEN="<your token>"

# PERSON_WATERMARK="2023-05-23 00:00:00"
# DEPARTMENT_WATERMARK="2023-05-23 00:00:00"

action="single-person-update"
person_ids='["80719647"]'
# action="full-person-load"

```

 - `LOCAL` being "True" makes use of the example files and not dynamo+Secrets Manager

 - `STACK` being `"developer"` skips ECS checks.

 - `DEBUG` will set the logging level to debug. There's a lot there though. 

 - You only need `SF_SECURITY_TOKEN` OR `SF_CLIENT_KEY` and `SF_CLIENT_SECRET`

 - `PERSON_WATERMARK` and `DEPARTMENT_WATERMARK` need to be of the format "YYYY-MM-DD HH:MM:SS", but they are optional, without them, they default to 1 day ago. 

### Actions

What is done is controlled by environment variables sent in to the app (through task definition overrides). 

Possible actions:

 - `single-person-update` requires an additional `person_ids` of the format "['huid', 'huid', 'huid']" so like, it actually does more than one, but let's say it's a single list? 

 - `full-person-load` this one doesn't require anything additional and just uses the existing `pds_query`

 - `person-updates` this one uses the person watermark

 - `full-department-load` this one doesn't require anything additonal and just uses the full department list

 - `department-updates` this one uses the department watermark



## TODO: Deployment Notes



## Notes on simple-salesforce

simple-salesforce is the most used Python salesforce integration library. We were also using simple-salesforce in the old HUDA API, but an older version. 

### Authenticating

Authentication is blissfully abstracted by the simple-salesforce library. It can use either an access token OR a client_key/secret to authenticate a use. 

If we were using the API, we would need to make a call to the token api and get a short lived token an pass that along with each call. The library keeps track of that internally. 

TODO: Credentials are needed in the environment, so they are passed through at the scheduling step. 

### Bulk API

The Salesforce Bulk API is the workhorse of this app. It can handle up to 10000 records at a time. The licenses I've seen thusfar have allowed 15000 Bulk API calls per (rolling) day. 

The Bulk API is an asynchronous API. That means you make a call to it, it starts a job, but it does not wait. It will return a job id. You can then use that job id to check on the status of the job. 

The way the Bulk functions work in simple-salesforce (by default) is they abstract the asynchronisity (that's totally a word, shut up) so when you make the call, it will, in the background, do the waiting for you, checking the job id and return when it's either finished or failed. 

This makes some of the logic easier, but it could lead to issues with performance unless we wrap the bulk calls in asyncio so we can be waiting on multiple jobs. 

NOTE: setting a value to `null` requires setting it to `#N/A`. (This is not easy to find in SF documentation.)

#### Examples

```py
data = [
    {
        'Id': 'aDm1R000000PLDgSAO',
        'HUDA__NAME_MIDDLE__c': 'test'
    }
]
sf.bulk.__getattr__('HUDA__hud_Name__c').upsert(data, external_id_field='Id')
```

### Getting data

Getting a single record is easy enough. This format could also be used to get "all records with a certain value". 
```py
contact = sf.Contact.get_by_custom_id('HUDA__hud_MULE_UNIQUE_PERSON_KEY__c', '88f5b068222b1f0c')
names = sf.__getattr__('HUDA__hud_Name__c').get_by_custom_id('HUDA__MULE_UNIQUE_PERSON_KEY__c', '88f5b068222b1f0c')
```

But most functions we're going to need are going to get more than one record at a time based on ids (like HUIDs or EPPNs), which means we need to leverage the SOQL endpoint. 
```py
sf_data = self.sf.query_all(f"SELECT Contact.id, HUDA__hud_UNIV_ID__c FROM Contact WHERE HUDA__hud_UNIV_ID__c IN('80719647')")
```
SOQL is a SQL-like syntax, but anytime you want to use something from SQL beyond `select blah from blah where blah`, you'll need to look it up. Also it doesn't join anything, so GL with that. 

## Other stuff

### Relationships

Most of the Objects in Salesforce are going to have a relationship to the Contact record of the person. Relationships are set and updated by simply sending the `Id` of the Contact (or other relationship). 

NOTE: this does NOT determine if someone sees a hud_Name when viewing a Contact record, that is determined by the external id on the Contact record. 

### Types

Types are validated in `salesforce.py` using the `validate` method.

 - `string`
 - `textarea`
 - `id`
 - `reference`
 - `email`
 - `date`
 - `datetime`
 - `double`