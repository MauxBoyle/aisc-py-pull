import os
import re
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

print("🔌 Connecting to Salesforce Core Engine...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. FETCH LIVE ACCOUNT ROLES, CONTACT DIRECTORY & LOCAL CASE CACHE
# =====================================================================
print("📡 Fetching live Account Junction details from Salesforce...")
acc_query = """
    SELECT Id, Name, 
           Cert_Certification_Contact__c, Cert_Principal_Contact__c, 
           Cert_Accounting_Contact__c, Cert_Marketing_contact__c
    FROM Account
"""
accounts_raw = sf.query_all(acc_query)
df_sf_accounts = pd.DataFrame(accounts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

print("📡 Fetching baseline Contact directory for lookup mappings...")
contacts_raw = sf.query_all("SELECT Id, FirstName, LastName, Email FROM Contact")
df_sf_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

# Create an instant Email-to-ContactID mapping dictionary
contact_email_to_id = {}
contact_email_to_name = {}
for c_id, row in df_sf_contacts.iterrows():
    email_clean = str(row.get('Email', '')).strip().lower()
    if email_clean:
        contact_email_to_id[email_clean] = c_id
        contact_email_to_name[email_clean] = f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()

# Load the local case tracking history cache to locate Parent Cases
HISTORY_FILE = "pu_cases_1mhistory.csv"
if os.path.exists(HISTORY_FILE):
    print(f"💾 Loading Case historical mapping cache from '{HISTORY_FILE}'...")
    df_history = pd.read_csv(HISTORY_FILE).set_index('AccountId')
else:
    print(f"⚠️ Warning: '{HISTORY_FILE}' missing. Case logs will print to terminal only.")
    df_history = pd.DataFrame()

# =====================================================================
# 2. LOAD STAGED SUBMISSIONS
# =====================================================================
STAGING_FILE = 'staged_contact_updates.csv'
if not os.path.exists(STAGING_FILE):
    print(f"❌ '{STAGING_FILE}' not found. Please run your staging script first.")
    exit()

print(f"💾 Reading staged submissions from '{STAGING_FILE}'...")
df_staged = pd.read_csv(STAGING_FILE).fillna('')

for col in df_staged.columns:
    df_staged[col] = df_staged[col].astype(str).str.replace(r'^nan$', '', flags=re.IGNORECASE, regex=True).str.strip()

# =====================================================================
# 3. CONSOLIDATE & EXECUTE PROCESSOR
# =====================================================================
grouped_submissions = df_staged.groupby('Account__c')

roles_schema_map = {
    'Certification Contact': ('Cert_Email__c', 'Cert_Certification_Contact__c'),
    'Principal Contact': ('Principal_Email__c', 'Cert_Principal_Contact__c'),
    'Accounting Contact': ('AP_Email__c', 'Cert_Accounting_Contact__c'),
    'Quality Contact': ('Quality_Email__c', 'Cert_Marketing_contact__c')
}

print(f"\n🕵️‍♂️ Reconciling Account Roles and posting case audit feeds...\n")

for account_id, group in grouped_submissions:
    if account_id not in df_sf_accounts.index:
        continue
        
    sf_acc = df_sf_accounts.loc[account_id]
    account_name = sf_acc['Name']
    
    # Locate the target processing case from our history cache file
    target_case_id = None
    if not df_history.empty and account_id in df_history.index:
        # Handle cases where multiple historical rows match the index by grabbing the latest row string
        case_row = df_history.loc[[account_id]]
        target_case_id = case_row.iloc[-1]['Id']

    print(f"🏢 ACCOUNT: {account_name} [{account_id}]")
    
    # Store pending updates to execute in a single unified API hit per Account
    pending_account_updates = {}
    case_chatter_logs = []
    
    for role_label, (staging_email_field, sf_lookup_field) in roles_schema_map.items():
        submitted_emails = set()
        for _, row in group.iterrows():
            em = str(row.get(staging_email_field, '')).strip().lower()
            if em:
                submitted_emails.add(em)
                
        if not submitted_emails:
            continue
            
        current_sf_contact_id = sf_acc.get(sf_lookup_field)
        
        # --- SCENARIO 1: MULTIPLICITY EXCEPTION ---
        if len(submitted_emails) > 1:
            err_msg = f"🛑 ROLE UPDATE FAILURE [{role_label}]: Conflict detected. Multiple conflicting emails submitted in this batch: {list(submitted_emails)}. Account update aborted for this role."
            print(f"     {err_msg}")
            case_chatter_logs.append(err_msg)
            
        # --- SCENARIO 2: SINGLE SUBMISSION EVALUATION ---
        elif len(submitted_emails) == 1:
            submitted_email = list(submitted_emails)[0]
            
            # Sub-Check A: Does the email address match an actual Salesforce Contact?
            if submitted_email not in contact_email_to_id:
                err_msg = f"⚠️ ROLE UPDATE FAILURE [{role_label}]: Submitted email '{submitted_email}' does not map to any active Contact ID in Salesforce. Account update aborted."
                print(f"     {err_msg}")
                case_chatter_logs.append(err_msg)
                continue
                
            target_contact_id = contact_email_to_id[submitted_email]
            target_contact_name = contact_email_to_name[submitted_email]
            
            # Sub-Check B: Is this an actual change or a redundant update?
            if target_contact_id == current_sf_contact_id:
                print(f"     🟢 [{role_label}]: No action required. '{target_contact_name}' is already assigned.")
            else:
                # Simple replacement criteria met! Queue it up.
                print(f"     ⚡ [{role_label}]: Queueing update ➡️ Assigning '{target_contact_name}' ({submitted_email})")
                pending_account_updates[sf_lookup_field] = target_contact_id
                case_chatter_logs.append(f"✅ ROLE UPDATE SUCCESS [{role_label}]: Automatically assigned '{target_contact_name}' ({submitted_email}) into this slot.")

    # =====================================================================
    # 4. COMMIT EXECUTION PASS TO SALESFORCE CORE
    # =====================================================================
    # Step A: Perform Live Account Field Updates if clear modifications exist
    if pending_account_updates:
        print(f"     💾 Writing live role field updates to Account record...")
        try:
            sf.Account.update(account_id, pending_account_updates)
            print("        🎉 Account updated successfully.")
        except Exception as e:
            print(f"        ❌ Failed to write update to Account: {e}")
            case_chatter_logs.append(f"❌ DATABASE ERROR: Failed to execute Account field update: {e}")

    # Step B: Log the Audit Trail to Case Chatter Feed
    if case_chatter_logs and target_case_id:
        chatter_payload = "\n".join(case_chatter_logs)
        # Format a clean system comment block block
        full_body = f"⚙️ AUTOMATED ACCOUNT ROLE UPDATE RUNTIME SUMMARY:\n{chatter_payload}"
        try:
            sf.FeedItem.create({'ParentId': target_case_id, 'Body': full_body})
            print(f"     📝 Posted runtime audit summary cleanly to Case ID {target_case_id} Chatter feed.")
        except Exception as e:
            print(f"     ❌ Failed to write Case Chatter log: {e}")
            
    print("-" * 60)
    print()
