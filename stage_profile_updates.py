import os
import re
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import clean_phone, fix_capitalization, format_key_questions
from datetime import datetime

load_dotenv()

PRIMARY_RESPONDER_ID = "005f200000A06i6AAB"

print("🔌 Connecting to Salesforce...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. FETCH RAW ENTRIES & BASELINE DATA
# =====================================================================
print("📡 Fetching raw submissions and baseline database layers...")

accounts_raw = sf.query_all("SELECT Id, Name, Certification_ID__c, BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry FROM Account")
df_accounts = pd.DataFrame(accounts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')
df_accounts['Clean_Cert_ID'] = df_accounts['Certification_ID__c'].astype(str).str.replace(r'\W+', '', regex=True).str.strip().str.upper()

contacts_raw = sf.query_all("SELECT Id, FirstName, LastName, Email, AccountId, Title, Phone FROM Contact")
df_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore')

pu_query = """
    SELECT Id, Name, Account__c, Comments__c, Other_Personnel_Notes__c, Certification_ID__c, Type__c, Email__c, Name__c, Status__c, Phone__c, Effective_Date__c,
           Existing_equipment_moved_to_new_facility__c, Will_new_equipment_be_purchased__c, Will_old_equipment_be_removed__c,
           Will_software_change__c, Will_QMS_or_documentation_change__c, Will_you_change_personnel__c, 
           Did_the_Cert_contact_change__c, Did_the_executive_manager_change__c,
           Cert_First_Name__c, Cert_Last_Name__c, Cert_Title__c, Cert_Email__c, Cert_Phone__c,
           Principal_First_Name__c, Principal_Last_Name__c, Principal_Title__c, Principal_Email__c, Principal_Phone__c,
           AP_First_Name__c, AP_Last_Name__c, AP_Title__c, AP_Email__c, AP_Phone__c,
           Quality_First_Name__c, Quality_Last_Name__c, QC_Title__c, Quality_Email__c, Quality_Phone__c,
           NY_Email__c, NY_First_Name__c, NY_Last_Name__c, NY_Phone__c,
           Revised_Company_Name__c, Revised_Company_Owner__c, Revised_Facility_Street__c, Revised_Facility_City__c, 
           Revised_Facility_State__c, Revised_Facility_Zip__c, Revised_Facility_Country__c, CreatedDate
    FROM Company_Profile_Change__c 
    WHERE Status__c = 'New'
"""
raw_pus = sf.query_all(pu_query)['records']
df_raw_pus = pd.DataFrame(raw_pus).drop(columns='attributes', errors='ignore')

if df_raw_pus.empty:
    print("ℹ️ No 'New' profile updates to stage. Environment clean.")
    exit()

# =====================================================================
# 2. ACCOUNT MATCHING & REPAIR LAYER
# =====================================================================
print("🩺 Healing broken or missing account mappings...")
healed_records = []

for _, row in df_raw_pus.iterrows():
    acc_id = row['Account__c']
    cert_id = str(row.get('Certification_ID__c', '')).strip()
    
    if pd.isna(acc_id) or acc_id == "":
        clean_target = ''.join(filter(str.isalnum, cert_id)).upper()
        matches = df_accounts[df_accounts['Clean_Cert_ID'] == clean_target]
        
        if not matches.empty:
            resolved_id = matches.index[0]
            sf.Company_Profile_Change__c.update(row['Id'], {'Account__c': resolved_id})
            row['Account__c'] = resolved_id
        else:
            sf.Task.create({
                'OwnerId': PRIMARY_RESPONDER_ID,
                'Subject': f"Investigate Orphaned Profile Update: {row['Name']}",
                'Description': f"Could not match Cert ID '{cert_id}' to an Account.",
                'Status': 'Not Started', 'Priority': 'Normal', 'WhatId': row['Id']
            })
            continue 
    healed_records.append(row)

df_staged_base = pd.DataFrame(healed_records)

# Partition by Submitter Update Type
df_key_raw = df_staged_base[df_staged_base['Type__c'] == 'Key Data'].copy()
df_contact_raw = df_staged_base[df_staged_base['Type__c'].isna() | (df_staged_base['Type__c'] == '')].copy()

# =====================================================================
# 3. PROCESSING TABLE A: KEY DATA ENRICHMENT
# =====================================================================
print("🏗️ Building Table A: Sanitizing Key Updates...")
key_updates_clean = []

for _, row in df_key_raw.iterrows():
    acc_id = row['Account__c']
    acc_info = df_accounts.loc[acc_id]
    
    # 1. Casing Fixes for Company Details
    row['Revised_Company_Name__c'] = fix_capitalization(row.get('Revised_Company_Name__c'))
    row['Revised_Company_Owner__c'] = fix_capitalization(row.get('Revised_Company_Owner__c'))
    row['Phone__c'] = clean_phone(row.get('Phone__c'))
    
    # 2. Address Backfill Logic
    addr_fields = ['Revised_Facility_Street__c', 'Revised_Facility_City__c', 'Revised_Facility_State__c', 'Revised_Facility_Zip__c', 'Revised_Facility_Country__c']
    has_partial_address = any(pd.notnull(row.get(f)) and str(row.get(f)).strip() != "" for f in addr_fields)
    
    if has_partial_address:
        row['Revised_Facility_Street__c'] = fix_capitalization(row.get('Revised_Facility_Street__c') or acc_info.get('BillingStreet'))
        row['Revised_Facility_City__c'] = fix_capitalization(row.get('Revised_Facility_City__c') or acc_info.get('BillingCity'))
        row['Revised_Facility_State__c'] = str(row.get('Revised_Facility_State__c') or acc_info.get('BillingState')).upper().strip()
        row['Revised_Facility_Zip__c'] = str(row.get('Revised_Facility_Zip__c') or acc_info.get('BillingPostalCode')).strip()
        row['Revised_Facility_Country__c'] = fix_capitalization(row.get('Revised_Facility_Country__c') or acc_info.get('BillingCountry'))
    
    # 3. Compile the Questionnaire Markdown Block
    row['Narrative_Questions_Block__c'] = format_key_questions(row)

    # Convert Timestamp string down to minute-level precision
    if pd.notnull(row.get('CreatedDate')):
        row['CreatedDate'] = str(row['CreatedDate'])[:16].replace('T', ' ')
    else:
        row['CreatedDate'] = datetime.today().strftime('%Y-%m-%d %H:%M')

    key_updates_clean.append(row)

df_key_updates = pd.DataFrame(key_updates_clean) if key_updates_clean else pd.DataFrame()

# =====================================================================
# 4. PROCESSING TABLE B: CONTACT ROLE SANITIZATION
# =====================================================================
print("🏗️ Building Table B: Sanitizing Contact Roles...")
contact_updates_clean = []

roles_prefix_map = {
    'Cert': ('Cert_First_Name__c', 'Cert_Last_Name__c', 'Cert_Title__c', 'Cert_Email__c', 'Cert_Phone__c'),
    'Principal': ('Principal_First_Name__c', 'Principal_Last_Name__c', 'Principal_Title__c', 'Principal_Email__c', 'Principal_Phone__c'),
    'AP': ('AP_First_Name__c', 'AP_Last_Name__c', 'AP_Title__c', 'AP_Email__c', 'AP_Phone__c'),
    'Quality': ('Quality_First_Name__c', 'Quality_Last_Name__c', 'QC_Title__c', 'Quality_Email__c', 'Quality_Phone__c')
}

for _, row in df_contact_raw.iterrows():
    acc_id = row['Account__c']
    
    # New York Submission Check
    ny_fields = ['NY_Email__c', 'NY_First_Name__c', 'NY_Last_Name__c', 'NY_Phone__c']
    row['Submitted_For_NY__c'] = any(pd.notnull(row.get(f)) and str(row.get(f)).strip() != "" for f in ny_fields)
    
    # Process General Submitter Phone to Dot Format
    row['Phone__c'] = clean_phone(row.get('Phone__c'))
    
    # Track fully completed roles for horizontal cross-filling
    fully_populated_roles = {}
    for role_pfx, fields in roles_prefix_map.items():
        if all(pd.notnull(row.get(f)) and str(row.get(f)).strip() != "" for f in fields):
            fully_populated_roles[role_pfx] = [str(row.get(f)).strip().lower() for f in fields]

    # Clean and patch each individual role tier
    for role_pfx, fields in roles_prefix_map.items():
        f_first, f_last, f_title, f_email, f_phone = fields
        
        vals = [str(row.get(f)).strip() if pd.notnull(row.get(f)) else "" for f in fields]
        non_null_count = sum(1 for v in vals if v != "")
        
        # --- ENHANCED CRM BACKFILL LOGIC ---
        # Catch Option A: Name is present but partial data holes exist (0 < non_null_count < 5)
        # Catch Option B: Name is blank, but an email was submitted (vals[3] != "")
        if (0 < non_null_count < 5) or (vals[0] == "" and vals[3] != ""):
            filled_via_cross_role = False
            
            # First, try horizontal cross-filling from another fully completed form role
            if vals[0] != "":
                for active_pfx, active_vals in fully_populated_roles.items():
                    if vals[0].lower() == active_vals[0]:
                        row[f_first], row[f_last], row[f_title], row[f_email], row[f_phone] = [f.title() if i != 3 else f for i, f in enumerate(active_vals)]
                        filled_via_cross_role = True
                        break
            
            # Second, if not cross-filled, query the live Salesforce contact cache
            if not filled_via_cross_role:
                account_contacts = df_contacts[df_contacts['AccountId'] == acc_id]
                
                # Dynamic Search Vector: Match by First Name OR Match by Email
                if vals[0] != "":
                    crm_matches = account_contacts[account_contacts['FirstName'].str.lower() == vals[0].lower()]
                else:
                    crm_matches = account_contacts[account_contacts['Email'].str.lower() == vals[3].lower()]
                    
                if not crm_matches.empty:
                    con_match = crm_matches.iloc[0]
                    # Backfill the staging row with real CRM data points
                    row[f_first] = row.get(f_first) or con_match['FirstName']
                    row[f_last] = row.get(f_last) or con_match['LastName']
                    row[f_title] = row.get(f_title) or con_match['Title']
                    row[f_email] = row.get(f_email) or con_match['Email']
                    row[f_phone] = row.get(f_phone) or con_match['Phone']
        
        # THE CRITICAL CLEANUP PASS
        row[f_first] = fix_capitalization(row.get(f_first))
        row[f_last] = fix_capitalization(row.get(f_last))
        row[f_title] = fix_capitalization(row.get(f_title))
        row[f_phone] = clean_phone(row.get(f_phone))

    # Convert Timestamp string down to minute-level precision
    if pd.notnull(row.get('CreatedDate')):
        row['CreatedDate'] = str(row['CreatedDate'])[:16].replace('T', ' ')
    else:
        row['CreatedDate'] = datetime.today().strftime('%Y-%m-%d %H:%M')

    # FIXED: Re-indented back inside the loop workspace context!
    contact_updates_clean.append(row)

# Instantiate the dataframe
df_contact_updates = pd.DataFrame(contact_updates_clean) if contact_updates_clean else pd.DataFrame()

print(f"✅ Staging Matrix Populated.")
print(f"   📊 Table A (Key Updates): {len(df_key_updates)} pristine rows.")
print(f"   📊 Table B (Contact Updates): {len(df_contact_updates)} pristine rows.")

# =====================================================================
# 5. DATA PERSISTENCE LAYER (COLUMNS SLICED EXCLUSIVELY)
# =====================================================================
print("💾 Writing pristine staging tables to disk...")

# Save Table A (Key Data) - DROPPING ROLES AND RAW QUESTION VARIABLES
if not df_key_updates.empty:
    KEY_COLUMNS_TO_KEEP = [
        'Id', 'CreatedDate', 'Name', 'Account__c', 'Certification_ID__c', 'Type__c', 'Email__c', 'Name__c', 'Status__c', 'Phone__c', 'Effective_Date__c',
        'Revised_Company_Name__c', 'Revised_Company_Owner__c', 'Revised_Facility_Street__c', 'Revised_Facility_City__c', 
        'Revised_Facility_State__c', 'Revised_Facility_Zip__c', 'Revised_Facility_Country__c', 'Narrative_Questions_Block__c'
    ]
    existing_key_cols = [col for col in KEY_COLUMNS_TO_KEEP if col in df_key_updates.columns]
    df_key_updates_filtered = df_key_updates[existing_key_cols].copy()
    
    # BULLETPROOF RECURSIVE NaN CLEANUP PASS
    for col in df_key_updates_filtered.columns:
        df_key_updates_filtered[col] = df_key_updates_filtered[col].astype(str).str.replace('nan', '', case=False).str.strip()
        
    df_key_updates_filtered.to_csv('staged_key_updates.csv', index=False)
    print("   💾 Generated 'staged_key_updates.csv' (Facility Restricted & NaN Free)")

# Save Table B (Contact Roles) - DROPPING UNWANTED FACILITY DATA
if not df_contact_updates.empty:
    CONTACT_COLUMNS_TO_KEEP = [
        'Id', 'CreatedDate', 'Name', 'Account__c', 'Certification_ID__c', 'Type__c', 'Email__c', 'Name__c', 'Status__c', 'Phone__c',
        'Cert_First_Name__c', 'Cert_Last_Name__c', 'Cert_Title__c', 'Cert_Email__c', 'Cert_Phone__c',
        'Principal_First_Name__c', 'Principal_Last_Name__c', 'Principal_Title__c', 'Principal_Email__c', 'Principal_Phone__c',
        'AP_First_Name__c', 'AP_Last_Name__c', 'AP_Title__c', 'AP_Email__c', 'AP_Phone__c',
        'Quality_First_Name__c', 'Quality_Last_Name__c', 'QC_Title__c', 'Quality_Email__c', 'Quality_Phone__c', 'Submitted_For_NY__c',
        'NY_Email__c', 'NY_First_Name__c', 'NY_Last_Name__c', 'NY_Phone__c'
    ]
    existing_contact_cols = [col for col in CONTACT_COLUMNS_TO_KEEP if col in df_contact_updates.columns]
    df_contact_updates_filtered = df_contact_updates[existing_contact_cols].copy()
    
    # BULLETPROOF RECURSIVE NaN CLEANUP PASS
    for col in df_contact_updates_filtered.columns:
        df_contact_updates_filtered[col] = df_contact_updates_filtered[col].astype(str).str.replace('nan', '', case=False).str.strip()
        
    df_contact_updates_filtered.to_csv('staged_contact_updates.csv', index=False)
    print("   💾 Generated 'staged_contact_updates.csv' (Role Restricted & NaN Free)")
