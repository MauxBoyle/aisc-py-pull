import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

print("🔌 Launching Profile Update Case-Contact Association Engine...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. FETCH RECENT PROFILE CASES MISSING CONTACT LINKS
# =====================================================================
print("📡 Fetching most recent Profile cases missing explicit Contact assignments...")
case_query = """
    SELECT Id, AccountId, Subject, Form_Email__c 
    FROM Case 
    WHERE ContactId = NULL 
    ORDER BY CreatedDate DESC 
    LIMIT 200
"""
cases_raw = sf.query_all(case_query)

if not cases_raw['records']:
    print("✅ System clear: Zero unlinked profile cases detected.")
    exit()

df_cases = pd.DataFrame(cases_raw['records']).drop(columns='attributes', errors='ignore')

# =====================================================================
# 2. CACHE ALL GLOBAL CONTACT RECOGNITION FINGERPRINTS
# =====================================================================
print("📡 Caching global Contact database directory (~42,000 records) into memory...")
# We pull standard Email alongside your custom Form_Email__c field for maximum coverage
contact_query = "SELECT Id, Email, Form_Email__c FROM Contact WHERE Email != NULL"
contacts_raw = sf.query_all(contact_query)
df_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore')

print("🗂️ Indexing global contact matrix for instant lookups...")
# Build two clean dictionary maps for frictionless O(1) processing speed
contact_by_standard_email = {}
contact_by_form_email = {}

for _, con in df_contacts.iterrows():
    c_id = con['Id']
    std_email = str(con.get('Email', '')).strip().lower()
    frm_email = str(con.get('Form_Email__c', '')).strip().lower()
    
    if std_email:
        contact_by_standard_email[std_email] = c_id
    if frm_email and frm_email != 'nan' and frm_email != '':
        contact_by_form_email[frm_email] = c_id

# =====================================================================
# 3. DIRECT IDENTIFICATION & ATTACHMENT LOOP
# =====================================================================
print("\n🕵️‍♂️ Resolving Case-Contact identities via explicit Form Email anchors...\n")

updates_executed = 0

for _, case in df_cases.iterrows():
    case_id = case['Id']
    
    # Extract the tracked submission email address recorded on the Case
    case_form_email = str(case.get('Form_Email__c', '')).strip().lower()
    
    if not case_form_email or case_form_email in ['nan', 'none', '']:
        # Fallback: If Form_Email__c is blank on this case, skip it for the general parsing script later
        continue
        
    matched_contact_id = None
    
    # Attempt Primary Vector Match: Match against Standard Email fields
    if case_form_email in contact_by_standard_email:
        matched_contact_id = contact_by_standard_email[case_form_email]
        
    # Attempt Secondary Vector Match: Match against historical Form_Email__c fields
    elif case_form_email in contact_by_form_email:
        matched_contact_id = contact_by_form_email[case_form_email]
        
    # Commit the link if an identification was confirmed
    if matched_contact_id:
        print(f"🚀 [LINK RESOLVED] Mapping Case {case_id} ➡️ Contact {matched_contact_id} via matching anchor ({case_form_email})")
        try:
            sf.Case.update(case_id, {'ContactId': matched_contact_id})
            updates_executed += 1
        except Exception as e:
            print(f"   ❌ Failed to write link to Salesforce: {e}")
    else:
        print(f"ℹ️ Case {case_id}: Submitter email '{case_form_email}' is completely new or unuploaded. Skipping link block.")

print(f"\n🎉 Sweep finished. Successfully attached {updates_executed} Profile Cases to verified database Contacts.")