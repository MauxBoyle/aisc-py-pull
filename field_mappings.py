# field_mappings.py

ACCOUNT_FIELDS = {
    'id': 'Id',
    'name': 'Name',
    'parent_id': 'ParentId',
    'industry': 'Industry',
    'billing_street': 'BillingStreet',
    'billing_city': 'BillingCity',
    'billing_state': 'BillingState',
    'billing_zip': 'BillingPostalCode',
    'company_owner': 'Company_Owner__c',
    'cert_contact_id': 'Cert_Certification_Contact__c',
    'principal_contact_id': 'Cert_Principal_Contact__c',
    'accounting_contact_id': 'Cert_Accounting_Contact__c',
    'quality_contact_id': 'Cert_Marketing_Contact__c'  # Standardized case typo fix
}

ROLE_METADATA = {
    'certification': {
        'label': 'Certification Contact',
        'account_lookup_field': ACCOUNT_FIELDS['cert_contact_id'],
        'staging_email': 'Cert_Email__c',
        'staging_first': 'Cert_First_Name__c',
        'staging_last': 'Cert_Last_Name__c',
        'staging_title': 'Cert_Title__c',
        'staging_phone': 'Cert_Phone__c'
    },
    'principal': {
        'label': 'Principal Contact',
        'account_lookup_field': ACCOUNT_FIELDS['principal_contact_id'],
        'staging_email': 'Principal_Email__c',
        'staging_first': 'Principal_First_Name__c',
        'staging_last': 'Principal_Last_Name__c',
        'staging_title': 'Principal_Title__c',
        'staging_phone': 'Principal_Phone__c'
    },
    'accounting': {
        'label': 'Accounting Contact',
        'account_lookup_field': ACCOUNT_FIELDS['accounting_contact_id'],
        'staging_email': 'AP_Email__c',      # Decoupled naming divergence
        'staging_first': 'AP_First_Name__c',
        'staging_last': 'AP_Last_Name__c',
        'staging_title': 'AP_Title__c',
        'staging_phone': 'AP_Phone__c'
    },
    'quality': {
        'label': 'Quality Contact',
        'account_lookup_field': ACCOUNT_FIELDS['quality_contact_id'],
        'staging_email': 'Quality_Email__c',
        'staging_first': 'Quality_First_Name__c',
        'staging_last': 'Quality_Last_Name__c',
        'staging_title': 'QC_Title__c',      # Standardized staging divergence
        'staging_phone': 'Quality_Phone__c'
    }
}