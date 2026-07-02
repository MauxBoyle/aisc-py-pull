import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import is_valid_explanation

load_dotenv()

# --- CONFIGURABLE GLOBAL VARIABLES ---
PRIMARY_RESPONDER_ID = "005f200000A06i6AAB"  # MB User ID
CERTIFICATION_QUEUE_ID = "00Gf2000005cagqEAA"  # Certification Queue ID
HISTORY_FILE = "pu_cases_1mhistory.csv"

# --- STEP 1: ESTABLISH CONNECTION ---
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# --- STEP 2: LOAD CURRENT CASES (The Duplicate Filter Set) ---
history_filename = 'pu_cases_history.csv'
try:
    df_history = pd.read_csv(history_filename)
    expected_mask = df_history['Subject'].str.startswith('Profile Update expected', na=False)
    existing_expected_accounts = set(df_history[expected_mask]['AccountId'].dropna())
    print(f"📋 Loaded {len(existing_expected_accounts)} accounts with existing 'Expected' cases from history.")
except FileNotFoundError:
    print(f"⚠️ '{history_filename}' not found. Creating a blank tracking sheet.")
    df_history = pd.DataFrame(columns=[
        'Id', 'Case.Name', 'ContactId', 'AccountId', 
        'Status', 'Subject', 'CreatedDate', 'LastModifiedDate'
    ])
    existing_expected_accounts = set()

# --- STEP 3: FETCH AUDITS ---
audit_query = """
    SELECT Id, Name, Cert_Account__c, Cert_Account__r.Name, Cert_Audit_Date__c,
           Cert_Contact__c, Explanation_for_Profile_Change_Form__c
    FROM Cert_Audit__c
    WHERE Company_Profile_Change_Form__c = TRUE
    AND Cert_Audit_Date__c = LAST_N_DAYS:30
"""

print("📡 Fetching audits based on true Audit Date (Last 30 Days)...")
audits = sf.query_all(audit_query)['records']

# --- STEP 4: TEXT SCRUBBING ENGINE ---
# is_valid_explanation function moved to utils

# --- STEP 5: AUTOMATION & ROUTING ---
print(f"⚙️ Evaluating {len(audits)} audits against filter matrices...")

# Temporary list to hold dictionaries of newly created cases
new_cases_logged = []

for audit in audits:
    audit_id = audit['Id']
    audit_number = audit['Name']
    account_id = audit['Cert_Account__c']
    explanation = audit['Explanation_for_Profile_Change_Form__c']
    audit_date = audit['Cert_Audit_Date__c']
    
    account_name = audit.get('Cert_Account__r', {}).get('Name', 'Unknown Account') if audit.get('Cert_Account__r') else 'Unknown Account'
    contact_id = audit.get('Cert_Contact__c')

    if account_id in existing_expected_accounts:
        print(f"⏭️ Filter Match: Case already exists for '{account_name}'. No new case needed.")
        continue

    if not is_valid_explanation(explanation):
        print(f"🛑 Text Scrub: Audit {audit_number} bypassed (Explanation: '{explanation}').")
        continue

    case_subject = f"Profile Update expected for {account_name}"
    case_comments = f"Explanation for Profile Change from {audit_number} on {audit_date}:\n{explanation}"

    case_payload = {
        'Subject': case_subject,
        'AccountId': account_id,
        'ContactId': contact_id,
        'OwnerId': CERTIFICATION_QUEUE_ID,                 
        'Primary_Responder__c': PRIMARY_RESPONDER_ID,    
        'Status': 'Pending',
        'Origin': 'Web',
        'Label_new__c': 'Auditing',                      
        'Sub_Label__c': 'Profile Change',
        'Description': ''                     
    }

    try:
        # A. Create Case
        new_case_res = sf.Case.create(case_payload)
        internal_id = new_case_res['id']
        
        # B. Retrieve Human-Readable Info
        case_info = sf.Case.get(internal_id)
        human_case_number = case_info['CaseNumber']
        
        print(f"🎉 Created Case {human_case_number} for {account_name}")

        # NEW: Inject your text blocks cleanly into the native INTERNAL COMMENTS section
        comment_payload = {
            'ParentId': internal_id,
            'CommentBody': case_comments,
            'IsPublished': False                         # Keeps the comment strictly INTERNAL (private)
        }
        sf.CaseComment.create(comment_payload)
        print(f"🔒 Internal Comments populated for Case {human_case_number}.")

        # C. Post Feed Item
        chatter_payload = {
            'ParentId': audit_id,
            'Body': f"Profile Change need noted. A pending case ({human_case_number}) has been made on the {account_name} account. -MB"
        }
        sf.FeedItem.create(chatter_payload)
        print(f"📝 Chatter logged on Audit {audit_number}.")

        # D. TRACK NEW CASE FOR LOCAL CSV UPDATE
        # We model this dictionary to perfectly match your CSV headers
        current_timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000+0000')
        new_case_row = {
            'Id': internal_id,
            'Case.Name': human_case_number,
            'ContactId': contact_id,
            'AccountId': account_id,
            'Status': 'Pending',
            'Subject': case_subject,
            'CreatedDate': current_timestamp,
            'LastModifiedDate': current_timestamp
        }
        new_cases_logged.append(new_case_row)

    except Exception as e:
        print(f"❌ Transaction failed for Audit {audit_number}: {e}")

# --- STEP 6: LOCAL CSV CACHE UPDATE ---
if new_cases_logged:
    print(f"\n💾 Updating '{history_filename}' with {len(new_cases_logged)} new cases...")
    df_new_cases = pd.DataFrame(new_cases_logged)
    
    # Concatenate the old history and the new cases together
    df_updated_history = pd.concat([df_history, df_new_cases], ignore_index=True)
    
    # Save back to the file system
    df_updated_history.to_csv(history_filename, index=False)
    print(f"✅ '{history_filename}' is now completely up to date.")
else:
    print("\nℹ️ No new cases were generated. CSV left as-is.")

print("🏁 Process complete.")