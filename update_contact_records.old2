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

for email, staged in unique_staged_contacts.items():
    account_id = staged['Account_Id']
    
    # -----------------------------------------------------------------
    # VECTOR A: THE EMAIL ADDRESS IS COMPLETELY UNRECOGNIZED (NET NEW)
    # -----------------------------------------------------------------
    if email not in df_sf_contacts.index:
        same_account_mask = df_sf_lookup_base['AccountId'] == account_id
        same_first_mask = df_sf_lookup_base['FirstName'].astype(str).str.strip().str.lower() == staged['First'].lower()
        same_last_mask = df_sf_lookup_base['LastName'].astype(str).str.strip().str.lower() == staged['Last'].lower()
        
        name_match_in_account = df_sf_lookup_base[same_account_mask & same_first_mask & same_last_mask]
        
        if not name_match_in_account.empty:
            existing_con = name_match_in_account.iloc[0]
            print(f"⚠️  [EMAIL ROTATION DETECTED] Contact Match Found by Name instead of Email!")
            print(f"   👤 Profile: {staged['First']} {staged['Last']} [Account ID: {account_id}]")
            print(f"   📍 CRM Record Saved Email: '{existing_con.get('Email') or '[Blank]'}' ➡️ New: '{email}'")
            print("-" * 50)
            print()
        else:
            # Cleanly pull the title string out of the uniqueness set
            submitted_titles = list(staged['Titles_Submitted'])
            resolved_title = submitted_titles[0] if len(submitted_titles) == 1 else ""
            
            print(f"🆕 [TRUE NET NEW CONTACT] Adding to Data Loader Buffer: {staged['First']} {staged['Last']}")
            
            # Append row mapped directly to your requested column naming spec
            net_new_contacts_collection.append({
                'AccountId': account_id,       # Data Loader maps this to standard Account ID field
                'FirstName': staged['First'],
                'LastName': staged['Last'],
                'Title': resolved_title,
                'Email': email,
                'Phone': staged['Phone']
            })
            
        continue 

    # -----------------------------------------------------------------
    # VECTOR B: EMAIL MATCH FOUND (STANDARD EXCEPTION BLOCK)
    # -----------------------------------------------------------------
    sf_matches = df_sf_contacts.loc[[email]]
    
    for _, sf_con in sf_matches.iterrows():
        discrepancies = []
        sf_contact_id = sf_con.get('Id')
        
        if staged['First'].lower() != str(sf_con.get('FirstName', '')).strip().lower():
            discrepancies.append(f"First Name mismatch ('{sf_con.get('FirstName')}' ➡️ '{staged['First']}')")
        if staged['Last'].lower() != str(sf_con.get('LastName', '')).strip().lower():
            discrepancies.append(f"Last Name mismatch ('{sf_con.get('LastName')}' ➡️ '{staged['Last']}')")
            
        sf_title = str(sf_con.get('Title', '')).strip()
        if sf_title.lower() in ['nan', 'none', 'null']: 
            sf_title = ""
            
        submitted_titles = list(staged['Titles_Submitted'])
        
        if sf_title == "":
            if len(submitted_titles) == 1:
                target_title = submitted_titles[0]
                print(f"⚡ [AUTOMATION] Updating blank Title for {email} to '{target_title}'...")
                try:
                    sf.Contact.update(sf_contact_id, {'Title': target_title})
                    print(f"   ✅ Successfully updated Salesforce Contact Record: {sf_contact_id}")
                    sf_title = target_title 
                except Exception as e:
                    print(f"   ❌ Failed live database update for {sf_contact_id}: {e}")
            elif len(submitted_titles) > 1:
                discrepancies.append(f"Title is blank in Salesforce, but multiple values provided: {submitted_titles}")
        else:
            if len(submitted_titles) == 1:
                staged_title = submitted_titles[0]
                if staged_title.lower() != sf_title.lower():
                    discrepancies.append(f"Title modification ('{sf_title}' ➡️ '{staged_title}')")
            elif len(submitted_titles) > 1:
                discrepancies.append(f"Title mismatch ('{sf_title}' ➡️ Multiple submitted: {submitted_titles})")
            
        if staged['Phone'] != "":
            norm_staged_phone = normalize_phone_compare(staged['Phone'])
            norm_sf_phone = normalize_phone_compare(sf_con.get('Phone'))
            norm_sf_mobile = normalize_phone_compare(sf_con.get('MobilePhone'))
            
            if norm_staged_phone == norm_sf_phone:
                pass 
            elif norm_staged_phone == norm_sf_mobile:
                discrepancies.append(f"ℹ️ NOTE: Submitted Phone matches CRM Mobile Phone perfectly ({staged['Phone']})")
            else:
                discrepancies.append(f"Phone number mismatch (CRM Main: '{sf_con.get('Phone') or '[Blank]'}', Mobile: '{sf_con.get('MobilePhone') or '[Blank]'}' ➡️ Submitted: '{staged['Phone']}')")

        if discrepancies:
            print(f"🚨 [DISCREPANCY] Contact Match Found: {email}")
            print(f"   👤 Current Profile: {staged['First']} {staged['Last']}")
            for bug in discrepancies:
                print(f"     📍 {bug}")
            print("-" * 50)
            print()

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
    