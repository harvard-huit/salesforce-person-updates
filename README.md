# Salesforce Person Updates

The salesforce-person-updates project pushes person data from the PDS to the specified Salesforce instance. 


## Development Notes

In order to work this locally, you'll need: 

### Apikey to the PDS

TODO: link to the PDS request form

### Test Salesforce instance

A sandbox or development or scratch Salesforce instance.

### .env file

A `.env` file that looks like:
```
STACK="developer"
PDS_APIKEY="<PDS Apikey>"
DEBUG="True"

SF_USERNAME="<your salesforce username>"
SF_PASSWORD="<your salesforce password>"
SF_DOMAIN="test"
# SF_CLIENT_KEY="<your client key>"
# SF_CLIENT_SECRET="<your client secret>"
SF_SECURITY_TOKEN="<your token>"
```

`STACK` being `"developer"` skips ECS checks.
`DEBUG` will set the logging level to debug. 

You only need `SF_SECURITY_TOKEN` OR `SF_CLIENT_KEY` and `SF_CLIENT_SECRET`

## TODO: Deployment Notes



## Workflow

This is an attempt to describe the workflow of this app. 

### 0. This app is triggered. 

### 1. Get confguration and data

#### PDS Query

This will be the query we use to initially limit data and get just the data we need. This will look something like `example_query.json`

#### Configuration

The config will look like the `example_config.json`.

#### Watermark

This controls when we last got updates. 

#### Credentials

Credentials are stored in Secrets Manager. The arn to the entries are in the Dynamo

### 2. Connect to Salesforce and Generate Metadata Maps

We get the metadata for all of the Salesforce Objects we're pushing to so we can do type validation before sending the data. 

### 3. Connect to the PDS and get the data we need

The query for the PDS is stored alongside other configurations in the Dynamo table. This can help limit what data it sorts through and improve speed while reducing space imprint.

### 4. Transform the PDS data into the Config format

This is the meat of the app, we're descifering what the mapping configuration means and creating a format for the bulk data API. 

### 5. Push data to Salesforce

We are using the Bulk API for this (through `simple-salesforce`). This API is typically asynchronous, however, we are using it synchronously so that we can "immediately" get feedback on if the call succeeded and log any issues. 

### 6. Everyone is happy. 

This is why we do what we do.



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