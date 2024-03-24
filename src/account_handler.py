from common import logger
from salesforce_person_updates import SalesforcePersonUpdates
from person_reference import PersonReference


class AccountHandler:
    def __init__(self, sfpu: SalesforcePersonUpdates):
        self.sfpu = sfpu

    def accounts_data_load(self):
        logger.info(f"Starting account data load")

        # using the pds_key here because it's the same key
        person_reference = PersonReference(apikey=self.sfpu.app_config.pds_apikey)

        record_type_ids = self.sfpu.hsf.get_record_type_ids('Account')

        if "account" in self.sfpu.app_config.watermarks and self.sfpu.app_config.watermarks["account"] is not None:
            watermark = self.sfpu.app_config.watermarks["account"]
        elif "department" in self.sfpu.app_config.watermarks and self.sfpu.app_config.watermarks["department"] is not None: 
            logger.warning(f"department watermark is deprecated, using account watermark moving forward")
            watermark = self.sfpu.app_config.watermarks["department"]
            # create watermark
            self.sfpu.app_config.watermarks["account"] = watermark
            self.sfpu.app_config.update_watermark("account")
        else:
            logger.warning(f"no watermark found for account -- no updates will be made to accounts")
            watermark = None

        # get accounts config
        account_configs = self.sfpu.app_config.config['Account']
        if not isinstance(account_configs, list):
            account_configs = [account_configs]

        
        sorted_configs = sorted(account_configs, key=lambda account: account['order'])

        
        for account_config in sorted_configs:
            source_type = account_config['source']

            if source_type == "schools":
                source_data = person_reference.getSchools()
            elif source_type == "departments":
                logger.error(f"departments not yet implemented")
                source_data = []
                continue
            elif source_type == "units":
                logger.error(f"units not yet implemented")
                source_data = []
                continue
            elif source_type == "sub_affiliations":
                logger.error(f"sub_affiliations not yet implemented")
                source_data = []
                continue
            elif source_type == "major_affiliations":
                logger.error(f"major_affiliations not yet implemented")
                source_data = []
                continue
            else:
                logger.error(f"source type {source_type} not recognized")
                source_data = []
                continue

            external_id = account_config['Id']['salesforce']
            source_id = account_config['Id']['source']

            # need a wrapper for the config to work with "legacy" methods that expect more full (and flat) configs
            account_config_wrapper = {
                "Account": account_config
            }
            self.sfpu.transformer.hashed_ids = self.sfpu.hsf.getUniqueIds(
                config=account_config_wrapper, 
                source_data=source_data
            )

            data = {}
            # data_gen = self.sfpu.transformer.transform(source_data=source_data, source_name='')
        
            logger.info(f"Finished account data load for {source_type}")



