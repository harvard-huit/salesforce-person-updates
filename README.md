# Salesforce Person Updates

The salesforce-person-updates project pushes person data from the PDS to the specified Salesforce instance. 

This is coupled loosely with / build alongside the [HUD Salesforce Package](https://github.huit.harvard.edu/HUIT/salesforce-harvard-data-package).

## Development Notes

In order to run this locally, you'll need: 

### Apikey to the PDS and or HR Departments API

TODO: link to the PDS request form

### Test Salesforce instance

A sandbox or development or scratch Salesforce instance and an admin-level integration user. 

### Environment Options

#### .env file

A `.env` file is the best way to work on this locally. Otherwise you'll need to have the data in an accessible dynamo table + secrets manager.  

<details>

<summary>
A local file would look like this
</summary>

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
person_ids=["80719647"]
# action="full-person-load"
```

</details>

 - `LOCAL` being "True" makes use of the example files and not dynamo+Secrets Manager

 - `STACK` being `"developer"` skips ECS checks.

 - `DEBUG` will set the logging level to debug. There's a lot there though so in general, you'll want this set to `False` (or unset). (This can be enabled on specific runs though to help find issues.)

 - You only need `SF_SECURITY_TOKEN` OR `SF_CLIENT_KEY` and `SF_CLIENT_SECRET`

 - `PERSON_WATERMARK` and `DEPARTMENT_WATERMARK` need to be of the format "YYYY-MM-DD HH:MM:SS", but they are optional, without them, they default to 1 day ago. 

#### Using Configurations in AWS Dynamo

If you have access and a configuration defined in DynamoDB, you can reference it with these environment variables:
 - `SALESFORCE_INSTANCE_ID` (example: `huit-full-sandbox`)
 - `TABLE_NAME` (example: `aais-services-salesforce-person-updates-dev`)

To use this, you must ensure the `LOCAL` env var is not set to `True` (or is unset).

(The only other environment variable strictly needed in addition to these is `STACK`) 

### Actions

What is done is controlled by environment variables sent in to the app (through task definition overrides). 

#### Possible actions:

 - `single-person-update` requires an additional `person_ids` of the format "['huid', 'huid', 'huid']" so like, it actually does more than one, but let's say it's a single list? 

 - `full-person-load` this one doesn't require anything additional and just uses the existing `pds_query`

 - `person-updates` this one uses the person watermark and will find updates to send along

 - `full-department-load` this one doesn't require anything additonal and just uses the full department list

 - `department-updates` this one uses the department watermark

 - `mark-not-updated` this one will check the ids (`eppn`s) in the Salesforce instance against those that can be queried (with the instance's PDS key). Ids that are not queryable are not being updated by this system and are marked by the "HUIT Updated" (`huit__Updated__c`) flag.

#### Local-only actions:

 - `delete-people` similar to `single-person-update` it can take a list of Ids and will (soft) delete them. This has no real-world application, but is useful in development / debugging.
 - `compare` this one requires a list of Ids and another Salesforce Instance (usually a production instance) that it will compare records against. The environment variables for the other instance should be in the following env vars:
   - `SF_USERNAME2` (example `integration_uds@harvard.edu`)
   - `SF_PASSWORD2` (example ... ah ah ah, almost got me!)
   - `SF_DOMAIN2` (example `test`/`login` (or unset for production))
   - `SF_CLIENT_KEY2` (example `?????????.???????????????????????.??????????????????==`)
   - `SF_CLIENT_SECRET2` (example `??????????????????????????????????????????????????????`)
   - `SF_SECURITY_TOKEN2` (example `????????????????????`)
     - (again, only a token OR client key/secret are required)



## Dynamo Table

An export of a valid (at the time of writing this) dynamo entry in the table can be found here in the root of this repository. 

The dynamo table includes a configuration, a pds query, and references to credentials stored in secrets manager. 

### Configuration

The configuration is the heart of this application. Each Salesforce instance will have its own configuration that will map fields from the PDS (and departments (and potentially other data sources)) to Objects in Salesforce. 

#### `source`

This defines which data set we're making use of for this object. For example, `departments` or `pds`.

#### `flat`

This helps visually and programatically identify which Objects will be 1:1 and which will be flattened. An example of a "flat" Object would be `Contact`. 

#### `Id`

The most important fields of an object are the `external id` we're using to confirm uniqueness. An Object in Salesforce needs to have an external id that will be unique/have meaning to the source system. (For example, a person role key or an eppn). This is what ensures that we update the appropriate records. 

The `Id` field in the config maps the external id field name in Salesforce to the external id field name in the source system. 

#### `when` conditional

There will be times when we have 2 values for a single field. For instance, a `Contact` record can only have one primary last name, but the PDS can return many. We could limit the names coming in by pearing down the PDS query, but they might also want all names pushed into another Object. In the HUDA implementation, this was the pre-defined `HUDA__hud_Names__c` Object. To handle this, a `when` operator was implemented to help control what gets populated in a flattened data set. 

##### default when

When we have multiple values for the same target field, sometimes we can't know if we'll get one, even with a defined `when`. For example, if we're looking for the email that has the `primaryEmailIndicator` set, because we don't have any kind of real MDM, we need to make a decision. As such, the default when is the value that has the latest updated date associated with it. 

#### `sf.*` References

The `sf` reference identifies source data that comes from Salesforce itself. This is necessary for gathering and defining reference fields. For example, relationship objects will have a reference to a `Contact` record. A query is done before relationship objects are processed to create a mapping of existing Contacts and the relationship fields they have. This is built from the `Id`s associated with the mapping. When a `Contact` reference is not found, it means it's a new relationship. 

#### Multiple Potential Sources

One of the more annoying aspects of the transform logic was creating a way for `employeeRoles`, `studentRoles`, and `poiRoles` to be merged into a single Object (`hed__Affiliation`). 

The way this was done was by having a target field be given an array of source fields. This indicates any of those fields would be able to be pushed into the target. 

```
  "HUDA__hud_PERSON_ROLES_KEY__c": ["employeeRoles.personRoleKey", "poiRoles.personRoleKey", "studentRoles.personRoleKey"],
  "HUDA__hud_EFF_STATUS__c": ["employeeRoles.effectiveStatus.code", "poiRoles.effectiveStatus.code", "studentRoles.effectiveStatus.code"],
  "HUDA__hud_EFFDT__c": ["employeeRoles.effectiveDate", "poiRoles.effectiveDate", "studentRoles.effectiveDate"],
```

To do this, it needs to loop through all possible values for each source record and if it finds one, uses that one. This was also done to work with the `Id` source fields. 

#### `static` Fields

A field is static when we're not actually getting it from a source, we're just setting it. Currently, the only `static` field in known use is to flag updated records. 

This indicates that that field will have a single, unchanging value. (In this case, huit_Updated__c will always be given the value of `true`).
```js
  "fields": {
      "huit__Updated__c": {
          "value": true,
          "static": true
      },
```




## Deployment Notes

Building and deployment will be done through Github Actions.

### Build Action

A build will take the code on the dev branch and assign it to a version tag. This image is then pushed to Artifactory.

The pattern being used here is `v0.0.0` for production images and `v0.0.0-dev` for beta/test versions. 

### Deploy Task Definition Action

A deploy action will push / update a task definition for a specific environment. It will assign a version tag to an environment. Please note this does not run anything, it just prepares the environment to be able to run. 

## Running

Running this application can be done a few ways. The two main ways are one-off runs (from Github Actions) and scheduled tasks. 

### Github Action Runs

A "run" will trigger from the Github Actions, but the action does not (can not?) report on success. In order to see that, you must (currently) look at the Splunk (or Salesforce) logs. 

 - **Spot Update**: this will run the `single-update-action` action given a comma separated list of ids (huids).
 - **Full Data Load**: this will run the `full-person-load` action. It will take some time. 


## Splunk Logs

Logs can be found on the HUIT Splunk instance: `https://harvard.splunkcloud.com/en-US/app/CADM_HUIT_AdminTS_AAIS/search`

Some useful queries:
 - **All logs**: `index="huit-admints-aais-dev" "attrs.APP_NAME"="salesforce-person-updates"`
 - **Errors**: `index="huit-admints-aais-dev" "attrs.APP_NAME"="salesforce-person-updates" error` (see what I did there?)

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