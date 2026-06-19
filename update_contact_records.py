import os
import re
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import evaluate_contacts_for_single_account

load_dotenv()

print("🔌 Connecting to Salesforce Core Engine...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. FETCH LIVE CONTACT MATRIX FROM CRM
# =====================================================================
print("📡 Fetching current live Contacts from Salesforce...")
contacts_raw = sf.query_all("SELECT Id, FirstName, LastName, Email, Title, Phone, MobilePhone, AccountId FROM Contact")
df_sf_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore')

df_sf_lookup_base = df_sf_contacts.copy()

df_sf_contacts['Email_Lower'] = df_sf_contacts['Email'].astype(str).str.strip().str.lower()
df_sf_contacts = df_sf_contacts.set_index('Email_Lower')

# =====================================================================
# 2. LOAD & CONSOLIDATE UNIQUE CONTACTS FROM STAGING
# =====================================================================
STAGING_FILE = 'staged_contact_updates.csv'
if not os.path.exists(STAGING_FILE):
    print(f"❌ '{STAGING_FILE}' not found. Please run 'stage_profile_updates.py' first.")
    exit()

print(f"💾 Reading staged submissions from '{STAGING_FILE}'...")
df_staged = pd.read_csv(STAGING_FILE).fillna('')

for col in df_staged.columns:
    df_staged[col] = df_staged[col].astype(str).str.replace(r'^nan$', '', flags=re.IGNORECASE, regex=True).str.strip()

unique_staged_contacts = {}

roles_config = {
    'Cert': ('Cert_First_Name__c', 'Cert_Last_Name__c', 'Cert_Title__c', 'Cert_Email__c', 'Cert_Phone__c'),
    'Principal': ('Principal_First_Name__c', 'Principal_Last_Name__c', 'Principal_Title__c', 'Principal_Email__c', 'Principal_Phone__c'),
    'AP': ('AP_First_Name__c', 'AP_Last_Name__c', 'AP_Title__c', 'AP_Email__c', 'AP_Phone__c'),
    'Quality': ('Quality_First_Name__c', 'Quality_Last_Name__c', 'QC_Title__c', 'Quality_Email__c', 'Quality_Phone__c')
}

for _, row in df_staged.iterrows():
    for role_label, fields in roles_config.items():
        f_first, f_last, f_title, f_email, f_phone = fields
        email = str(row.get(f_email, '')).strip().lower()
        
        if not email or email == "":
            continue
            
        first = str(row.get(f_first, '')).strip()
        last = str(row.get(f_last, '')).strip()
        title = str(row.get(f_title, '')).strip()
        phone = str(row.get(f_phone, '')).strip()
        account_id = str(row.get('Account__c', '')).strip()
        
        if email not in unique_staged_contacts:
            unique_staged_contacts[email] = {
                'First': first, 'Last': last, 'Phone': phone, 'Account_Id': account_id,
                'Titles_Submitted': set([title]) if title else set()
            }
        else:
            unique_staged_contacts[email]['Account_Id'] = account_id
            
            if title:
                unique_staged_contacts[email]['Titles_Submitted'].add(title)
            if not unique_staged_contacts[email]['Phone'] and phone:
                unique_staged_contacts[email]['Phone'] = phone

def normalize_phone_compare(p_str):
    if not p_str or pd.isna(p_str):
        return ""
    digits = re.sub(r'\D', '', str(p_str))
    if len(digits) == 11 and digits.startswith('1'):
        return digits[1:]
    return digits

# =====================================================================
# 4. RECONCILIATION & DATA LOADER COLLECTION LOOP
# =====================================================================
print(f"\n🕵️‍♂️ Running deep verification across unique matched contacts...\n")

# Array to hold our Data Loader-ready row payloads
net_new_contacts_collection = []

print(f"\n🕵️‍♂️ Running deep verification across unique matched contacts via centralized utils engine...\n")
net_new_contacts_collection = []
grouped_submissions = df_staged.groupby('Account__c')

for account_id, group in grouped_submissions:
    # Run the cannibalized single-account verification engine
    res = evaluate_contacts_for_single_account(account_id, group, df_sf_contacts, contact_email_to_id, contact_email_to_name)
    
    # 1. Handle Automated Title Patches Instantly
    for patch in res['automated_title_patches']:
        print(f"⚡ [AUTOMATION] Updating blank Title for {patch['Email']} to '{patch['TargetTitle']}'...")
        sf.Contact.update(patch['ContactId'], {'Title': patch['TargetTitle']})
        
    # 2. Output standard console alerts for straightforward manual discrepancies
    for issue_pkg in res['straightforward_reviews']:
        print(f"🚨 [DISCREPANCY] Contact Match Found: {issue_pkg['Email']} ({issue_pkg['Name']})")
        for issue in issue_pkg['Issues']:
            print(f"     📍 {issue}")
            
    # 3. Handle Net New row tracking collections
    if res['net_new_loader_rows']:
        for new_row in res['net_new_loader_rows']:
            print(f"🆕 [TRUE NET NEW CONTACT] Adding to Data Loader Buffer: {new_row['FirstName']} {new_row['LastName']}")
            net_new_contacts_collection.append(new_row)

# ... [Keep your final section 5 Data Loader CSV output block exactly the same] ...
🏢 The Upgraded reconcile_account_roles.py
Open reconcile_account_roles.py, look inside your main processing loop block, and strip it down to use your centralized utils function:

Python
# ... [Keep your initial imports, simple_salesforce queries, and history CSV reads intact] ...

from utils import propose_account_role_swaps_for_single_account

print(f"\n🕵️‍♂️ Reconciling Account Roles and posting case audit feeds via centralized utils engine...\n")

for account_id, group in grouped_submissions:
    if account_id not in df_sf_accounts.index: continue
    
    sf_acc = df_sf_accounts.loc[account_id]
    account_name = sf_acc['Name']
    print(f"🏢 ACCOUNT: {account_name} [{account_id}]")
    
    # Call the centralized role matching engine
    res = propose_account_role_swaps_for_single_account(account_id, group, sf_acc, contact_email_to_id, contact_email_to_name, df_sf_contacts)
    
    pending_account_updates = {}
    case_chatter_logs = []

    # Handle Perfect Alignments
    for match in res['perfect_matches']:
        print(f"     🟢 {match}")

    # Handle Multiplicity Block Exceptions
    for conflict in res['multiplicity_conflicts']:
        err = f"🛑 ROLE UPDATE FAILURE [{conflict['Role']}]: Conflict detected. Multiple conflicting emails: {conflict['Emails']}."
        print(f"     {err}")
        case_chatter_logs.append(err)

    # Handle Missing Contact Id Warnings
    for unknown in res['unknown_emails']:
        err = f"⚠️ ROLE UPDATE FAILURE [{unknown['Role']}]: Email '{unknown['Email']}' does not map to any active Contact ID."
        print(f"     {err}")
        case_chatter_logs.append(err)

    # Queue Simple Substitutions
    for swap in res['proposed_swaps']:
        print(f"     ⚡ [{swap['Role']}]: Queueing update -> Assigning '{swap['Name']}'")
        pending_account_updates[swap['Field']] = swap['ContactId']
        case_chatter_logs.append(f"✅ ROLE UPDATE SUCCESS [{swap['Role']}]: Automatically assigned '{swap['Name']}'.")

# =====================================================================
# 5. DATA LOADER CSV OUTPUT LAYER (NEW)
# =====================================================================
print("💾 Saving Data Loader export payload...")
if net_new_contacts_collection:
    df_output = pd.DataFrame(net_new_contacts_collection)
    df_output.to_csv('net_new_contacts.csv', index=False)
    print(f"   🎉 SUCCESS: Generated 'net_new_contacts.csv' with {len(df_output)} pristine insert-ready rows.")
else:
    print("   ℹ️ No true net-new contacts found in this batch to export.")