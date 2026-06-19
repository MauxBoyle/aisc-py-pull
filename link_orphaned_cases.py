import os
import re
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

print("🔌 Launching Standalone Case-Contact Attachment Engine...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# 1. Fetch Cases missing a Contact ID link
print("📡 Scanning for orphaned Cases missing Contact assignments...")
case_query = "SELECT Id, AccountId, Subject, Description FROM Case WHERE ContactId = NULL AND AccountId != NULL LIMIT 200"
cases_raw = sf.query_all(case_query)

if not cases_raw['records']:
    print("✅ System clean: Zero orphaned cases detected.")
    exit()

df_cases = pd.DataFrame(cases_raw['records']).drop(columns='attributes', errors='ignore')

# 2. Extract unique Account IDs to optimize our Contact lookup search
account_ids = tuple(df_cases['AccountId'].unique())
# Handle single-item formatting safe-guards for SQL IN clauses
acc_filter = f"('{account_ids[0]}')" if len(account_ids) == 1 else str(account_ids)

print(f"📡 Fetching Contact directory for {len(account_ids)} associated corporate accounts...")
contact_query = f"SELECT Id, FirstName, LastName, Email, AccountId FROM Contact WHERE AccountId IN {acc_filter}"
contacts_raw = sf.query_all(contact_query)
df_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore')

# 3. Match and Bind
print("\n🕵️‍♂️ Running logical regex text-matching sweeps across orphans...\n")

for _, case in df_cases.iterrows():
    case_id = case['Id']
    acc_id = case['AccountId']
    combined_text = f"{case.get('Subject', '')} {case.get('Description', '')}".lower()
    
    # Isolate contacts belonging strictly to this Case's Account
    sub_contacts = df_contacts[df_contacts['AccountId'] == acc_id]
    
    match_found = False
    for _, contact in sub_contacts.iterrows():
        email = str(contact.get('Email', '')).strip().lower()
        
        # Vector A: Match by clear explicit email reference inside the text dump
        if email and email in combined_text:
            print(f"⚡ [MATCH FOUND] Binding Case {case_id} to Contact {contact['Id']} via email fingerprint ({email})")
            sf.Case.update(case_id, {'ContactId': contact['Id']})
            match_found = True
            break
            
    if not match_found:
        print(f"ℹ️ Case {case_id}: Unable to auto-resolve identity. No matching email signatures detected in case text block.")

print("\n🎉 Case-Contact attachment sweep finished successfully.")