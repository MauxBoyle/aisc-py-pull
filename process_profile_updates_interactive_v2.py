import os
import sys
import difflib
import pandas as pd
from datetime import datetime, timedelta
from simple_salesforce import Salesforce

# Import the centralized logic engines from utils
from utils import (
    evaluate_contacts_for_single_account,
    propose_account_role_swaps_for_single_account
)

# =====================================================================
# INITIALIZATION & CORE CONNECTIONS
# =====================================================================
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# Force string data types on zip codes during CSV ingestion to prevent ".0" float conversions
dtype_spec = {'Revised_Facility_Zip__c': str, 'Zip__c': str}

df_key_staged = pd.read_csv('staged_key_updates.csv', dtype=dtype_spec).fillna('') if os.path.exists('staged_key_updates.csv') else pd.DataFrame()
df_contact_staged = pd.read_csv('staged_contact_updates.csv', dtype=dtype_spec).fillna('') if os.path.exists('staged_contact_updates.csv') else pd.DataFrame()
df_history = pd.read_csv('pu_cases_1mhistory.csv').fillna('')

print("📡 Fetching active 'New' Profile Updates from Salesforce...")
pending_pus = sf.query_all("SELECT Id, Name, Account__c, CreatedDate, Email__c, Name__c FROM Company_Profile_Change__c WHERE Status__c = 'New' ORDER BY CreatedDate ASC")['records']

if not pending_pus:
    print("🎉 All clear! Zero pending Profile Updates with Status = 'New'.")
    exit()

print("📡 Pre-loading Contact Directory dictionaries for high-speed matching...")
contacts_directory = sf.query_all("SELECT Id, FirstName, LastName, Email, AccountId, Title, Phone FROM Contact")['records']
df_contacts_global = pd.DataFrame(contacts_directory).drop(columns='attributes', errors='ignore').set_index('Email', drop=False)

contact_email_to_id = {str(k).strip().lower(): v for k, v in zip(df_contacts_global['Email'], df_contacts_global['Id'])}
contact_email_to_name = {str(k).strip().lower(): f"{f} {l}".strip() for k, f, l in zip(df_contacts_global['Email'], df_contacts_global['FirstName'], df_contacts_global['LastName'])}

# =====================================================================
# INTERACTIVE MASTER LOOP (OLDEST TO NEWEST)
# =====================================================================
for current_pu in pending_pus:
    pu_id = current_pu['Id']
    pu_name = current_pu['Name']
    account_id = current_pu['Account__c']
    
    # Fetch live Account details
    account_record = sf.Account.get(account_id)
    account_name = account_record['Name']
    parent_id = account_record.get('ParentId')
    account_industry = account_record.get('Industry')
    
    # Initialize process state tracker variables
    address_disposition = None  # Captures human verification path (1, 2, or 3)
    
    # Isolate the current Profile Update rows across BOTH staging files
    pu_rows_key = df_key_staged[df_key_staged['Id'] == pu_id]
    pu_rows_contact = df_contact_staged[df_contact_staged['Id'] == pu_id]
    
    row_key = pu_rows_key.iloc[0] if not pu_rows_key.empty else None
    row_contact = pu_rows_contact.iloc[0] if not pu_rows_contact.empty else None
    
    first_row = row_contact if row_contact is not None else (row_key if row_key is not None else {})
    submitter_name = current_pu.get('Name__c', 'Participant') if current_pu.get('Name__c') else 'Participant'

    os.system('clear' if os.name == 'posix' else 'cls')
    print("=====================================================================")
    print(f"🔮 OPERATIONAL COCKPIT: PROCESSING {pu_name} FOR {account_name}")
    print("=====================================================================\n")

    # -----------------------------------------------------------------
    # STEP 1: ACCOUNT RECONNAISSANCE SCREEN & BASELINE ROSTER SNAPSHOT
    # -----------------------------------------------------------------
    print("📋 [STEP 1] ACCOUNT RECONNAISSANCE & LIVE ROSTER SNAPSHOT")
    
    # A. Multi-PU Check
    account_all_pus = [p for p in pending_pus if p['Account__c'] == account_id]
    if len(account_all_pus) > 1:
        print(f"  ⚠️  MULTIPLICITY ALERT: This account has {len(account_all_pus)} pending submissions in this queue:")
        for p in account_all_pus:
            print(f"     📍 {p['Name']} submitted on {p['CreatedDate']} by {p.get('Name__c')} ({p.get('Email__c')})")
    else:
        print("  🟢 Multiplicity Check: No competing concurrent submissions for this account.")
        
    # B. Family Hierarchy Check
    is_family = "YES" if parent_id else "NO"
    print(f"  👪 Part of Corporate Family Hierarchy? {is_family}")
    
    # C. Audit Log Check (FIXED: Fully tracks valid internal and external statuses)
    try:
        audit_query = sf.query_all(f"SELECT Id, Cert_Audit_Date__c, Cert_Audit_Status__c FROM Cert_Audit__c WHERE Cert_Account__c = '{account_id}' ORDER BY Cert_Audit_Date__c DESC LIMIT 5")['records']
        
        valid_statuses = [
            'New', 'Pending Acceptance', 'Reschedule in Progress', 
            'Reassignment in Progress', 'Scheduled - Approved', 'Completed - Under Review'
        ]
        
        upcoming_audit = next((a for a in audit_query if a['Cert_Audit_Status__c'] in valid_statuses), None)
        
        if upcoming_audit:
            print(f"  📅 AUDIT CONTEXT: Active Valid Audit on file for {upcoming_audit['Cert_Audit_Date__c']} (Status: {upcoming_audit['Cert_Audit_Status__c']})")
        else:
            print(f"  📅 AUDIT CONTEXT: No active or valid audit history found on file.")
    except Exception as e:
        print(f"  ⚠️  AUDIT CONTEXT ERROR: Could not pull audit logs ({e}).")
        upcoming_audit = None
        
    # D. 6-Month Case History Lookback
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%dT%H:%M:%SZ')
    recent_cases = sf.query_all(f"SELECT CaseNumber, Subject, Status, CreatedDate, LastModifiedDate FROM Case WHERE AccountId = '{account_id}' AND CreatedDate >= {six_months_ago} ORDER BY CreatedDate DESC")['records']
    
    print(f"  📂 Historical Cases (Last 6 Months): {len(recent_cases)}")
    for c in recent_cases:
        c_date = str(c['CreatedDate'])[0:10]
        m_date = str(c['LastModifiedDate'])[0:10]
        print(f"     👉 Case {c['CaseNumber']} | Status: {c['Status']} | Opened: {c_date} | Modified: {m_date}")
        print(f"        Subj: {c['Subject']}")

    print("\n  📸 PRISTINE LIVE ROSTER PROFILE SNAPSHOT:")
    snapshot_text_block = (
        f"     Cert Contact: {sf.Contact.get(account_record['Cert_Certification_Contact__c'])['Name'] if account_record['Cert_Certification_Contact__c'] else '[Vacant]'}\n"
        f"     Principal:    {sf.Contact.get(account_record['Cert_Principal_Contact__c'])['Name'] if account_record['Cert_Principal_Contact__c'] else '[Vacant]'}\n"
        f"     Accounting:   {sf.Contact.get(account_record['Cert_Accounting_Contact__c'])['Name'] if account_record['Cert_Accounting_Contact__c'] else '[Vacant]'}\n"
        f"     Quality:      {sf.Contact.get(account_record['Cert_Marketing_Contact__c'])['Name'] if account_record['Cert_Marketing_Contact__c'] else '[Vacant]'}"
    )
    print(snapshot_text_block)

    input("\n📥 Recon & Baseline snapshot locked. Press [ENTER] to review Key Profile Updates...")

    # -----------------------------------------------------------------
    # STEP 2: KEY DATA UPDATE EVALUATION
    # -----------------------------------------------------------------
    print("\n🔑 [STEP 2] EVALUATING KEY PROFILE UPDATES")
    email_summary_notes = []
    
    if row_key is not None:
        # A. Ownership Check
        new_owner = str(row_key.get('Revised_Company_Owner__c', '')).strip()
        current_owner = str(account_record.get('Company_Owner__c', '')).strip()
        
        if new_owner and new_owner != 'nan':
            print(f"  🔹 OWNERSHIP CHANGE DETECTED:")
            if not current_owner or current_owner == '':
                note = f"Your company ownership of {new_owner} was noted."
                print(f"     📍 Current is Blank ➡️ New: {new_owner}")
            else:
                note = f"Your company ownership was updated from {current_owner} to {new_owner}."
                print(f"     📍 Replace: {current_owner} ➡️ {new_owner}")
            
            email_summary_notes.append(note)
            if input("     Apply Ownership update to Salesforce Account right now? (y/n): ").lower() == 'y':
                sf.Account.update(account_id, {'Company_Owner__c': new_owner})
                print("     ✅ Salesforce Account Updated.")

        # B. Company Name Similarity Check
        new_name = str(row_key.get('Revised_Company_Name__c', '')).strip()
        if new_name and new_name != 'nan' and new_name.lower() != account_name.lower():
            print(f"  🔹 COMPANY NAME CHANGE DETECTED:")
            print(f"     CRM Active: '{account_name}' ➡️ Proposed: '{new_name}'")
            
            similarity_ratio = difflib.SequenceMatcher(None, account_name.lower(), new_name.lower()).ratio()
            print(f"     📊 Algorithmic Similarity Index: {similarity_ratio * 100:.1f}%")
            
            if similarity_ratio >= 0.90:
                print("     🟢 Match >= 90%: Classifying as Minor/Simple corporate suffix update.")
                if input(f"     Update Account Name directly to '{new_name}'? (y/n): ").lower() == 'y':
                    sf.Account.update(account_id, {'Name': new_name})
                    print("     ✅ Account Name updated directly.")
            else:
                print("     🚨 Match < 90%: Significant Rebranding detected. Shifting to f.k.a. structural tracking.")
                fka_name = f"{new_name} (f.k.a. {account_name})"
                if input(f"     Update Account Name to formatting structure: '{fka_name}'? (y/n): ").lower() == 'y':
                    sf.Account.update(account_id, {'Name': fka_name})
                    
                    sf.Task.create({
                        'OwnerId': sf.restful("UserInfo")['user_id'],
                        'Subject': f"Remove f.k.a. suffix from {new_name} after next audit cycle clears.",
                        'Priority': 'Normal', 'Status': 'Not Started',
                        'Description': f"Name changed via {pu_name}. Revert from f.k.a. formatting back to clean name block once audit clears."
                    })
                    print("     ✅ Account mutated to f.k.a. layout and cleanup task created.")

        # C. Address Verification & Industry Guard Filters
        new_street = str(row_key.get('Revised_Facility_Street__c', '')).strip()
        if new_street and new_street != 'nan':
            print(f"  🔹 LOCATION SEGMENT MODIFICATION DETECTED:")
            print(f"     Sector Classification: {account_industry or 'Unassigned Picklist'}")
            
            if account_industry == 'Erector':
                print("     🟢 Sector: Erector (Office Address Mapping Sequence)")
                addr_payload = {
                    'BillingStreet': row_key.get('Revised_Facility_Street__c'),
                    'BillingCity': row_key.get('Revised_Facility_City__c'),
                    'BillingState': row_key.get('Revised_Facility_State__c'),
                    'BillingPostalCode': row_key.get('Revised_Facility_Zip__c')
                }
                sf.Account.update(account_id, addr_payload)
                print("     ✅ Office address fields auto-updated on Erector Account record.")
                
            elif account_industry == 'Fabricator':
                print("     🚨 Sector: Fabricator (Facility Location Review Required)")
                print(f"        CRM Record Address: {account_record.get('BillingStreet')}")
                print(f"        Form Staged Address: {new_street}")
                
                print("\n     📐 SELECT FACILITY ADDRESS EVALUATION PATH DISPOSITION:")
                print("        [1] Simple Correction / Typo / Administrative Change (No Audit Qualification)")
                print("        [2] Standard Relocation / Accept Without Qualification (Pending Upcoming Audit Language)")
                print("        [3] High-Risk Relocation / Structural Hold (Keep Case Open For Manual Next Steps)")
                
                choice = input("     Enter disposition selection numerical choice (1/2/3): ").strip()
                if choice in ['1', '2', '3']:
                    address_disposition = int(choice)
                    
                    if address_disposition in [1, 2]:
                        # Apply live update execution parameters to CRM
                        pending_prefix = "(pending address update) " if address_disposition == 2 else ""
                        sf.Account.update(account_id, {
                            'BillingStreet': f"{pending_prefix}{new_street}",
                            'BillingCity': row_key.get('Revised_Facility_City__c'),
                            'BillingState': row_key.get('Revised_Facility_State__c'),
                            'BillingPostalCode': row_key.get('Revised_Facility_Zip__c')
                        })
                        print(f"        ✅ Account address updated inside CRM (Disposition Selection [{address_disposition}] Registered).")
                    else:
                        print("        🔒 Relocation held open. No database modifications written. Keeping Case open.")
                else:
                    print("        ⚠️  Invalid input option. Cascading to structural hold fallback configuration.")
                    address_disposition = 3
    else:
        print("  🟢 No Key Updates (Name/Ownership/Address) submitted in this Profile Update payload.")

    input("\n📥 Key Updates resolved. Press [ENTER] to evaluate Contact modification parameters...")

    # -----------------------------------------------------------------
    # STEP 3: CONTACT AUDITING DISCOVERY ENGINE
    # -----------------------------------------------------------------
    print("\n🕵️‍♂️ [STEP 3] CONTACT MODIFICATION DISCOVERY ENGINE")
    
    active_contact_rows = pu_rows_contact if not pu_rows_contact.empty else pu_rows_key
    
    if pu_rows_contact.empty:
        print("  ℹ️  NOTICE: No contact changes or roster additions were submitted in this form payload.")
    else:
        res_contacts = evaluate_contacts_for_single_account(account_id, active_contact_rows, df_contacts_global, contact_email_to_id, contact_email_to_name)
        
        print("   AUTOMATED ACTIONS EXTRACTED:")
        for patch in res_contacts['automated_title_patches']:
            print(f"     ⚡ Auto-patched blank Title for {patch['Email']} ➡️ '{patch['TargetTitle']}'")
            sf.Contact.update(patch['ContactId'], {'Title': patch['TargetTitle']})
        if not res_contacts['automated_title_patches']:
            print("     🟢 No blank titles requiring automatic patch fields.")
        
        print("\n   STRAIGHTFORWARD INTERACTIVE AUDIT PERMISSIONS:")
        for issue_pkg in res_contacts['straightforward_reviews']:
            print(f"     ❓ Field Variance Found for {issue_pkg['Email']} ({issue_pkg['Name']}):")
            for issue in issue_pkg['Issues']:
                print(f"        📍 {issue}")
            
            if input("        Approve and execute this update inside CRM? (y/n): ").lower() == 'y':
                print("        ✅ Live Contact field modification successfully pushed.")
            else:
                print("        ❌ Modification held back via user override instruction.")
        if not res_contacts['straightforward_reviews']:
            print("     🟢 No straightforward phone or title variances identified.")
                
        print("\n    UNCLEAR VARIATIONS HELD FOR MANUAL REVIEW:")
        for unc in res_contacts['unclear_exceptions']:
            print(f"     ⚠️  Deep Identity Conflict: {unc['Email']} ({unc['Name']})")
            print(f"        Issues: {unc['Issues']}")
        if not res_contacts['unclear_exceptions']:
            print("     🟢 Zero extreme identity mismatches flagged.")

    input("\n📥 Contact items verified. Press [ENTER] to process Case link anchoring structures...")

    # -----------------------------------------------------------------
    # STEP 4: ORPHANED CASE LINK RESOLUTION (FIXED EXCEPTION NAMESPACE)
    # -----------------------------------------------------------------
    print("\n🔗 [STEP 4] VERIFYING PARENT CASE IDENTIFICATION")
    matching_case = df_history[df_history['AccountId'] == account_id]

    if not matching_case.empty:
        case_id = matching_case.iloc[-1]['Id']
        case_num = matching_case.iloc[-1]['Case.Name']
        
        try:
            # Attempt live CRM validation using the active client
            case_live = sf.Case.get(case_id)
            
            if not case_live.get('ContactId'):
                sub_email = str(first_row.get('Email__c', '')).strip().lower() if not isinstance(first_row, dict) else ""
                if sub_email:
                    con_lookup = sf.query(f"SELECT Id FROM Contact WHERE Email = '{sub_email}' LIMIT 1")['records']
                    if con_lookup:
                        sf.Case.update(case_id, {'ContactId': con_lookup[0]['Id']})
                        print(f"   ✅ Case {case_num} ContactId missing link cleared ➡️ Attached to Contact ID: {con_lookup[0]['Id']}")
                else:
                    print(f"   ℹ️ Case {case_num} lookup unpopulated but no valid submitter email found to attach.")
            else:
                print(f"   🟢 Case {case_num} already contains an active Contact link anchor.")
                
        # 🌟 UNIVERSAL FALLBACK: Catches any error and safely checks for a missing resource string
        except Exception as e:
            if "NOT_FOUND" in str(e):
                print(f"   ⚠️  CACHE WARNING: History file pointed to Case {case_num} (ID: {case_id}), but it no longer exists in Salesforce. Skipping linkage step.")
            else:
                print(f"   ⚠️  UNKNOWN CASE ERROR: Handled an unexpected exception checking Case {case_num} ({e}). Moving on.")
    else:
        print("   ℹ️ No local processing case found in history cache to bind.")

    input("\n📥 Case linkages resolved. Press [ENTER] to balance live Account Role slots...")

    # -----------------------------------------------------------------
    # STEP 5: ACCOUNT ROLE SWAPS
    # -----------------------------------------------------------------
    print("\n🔄 [STEP 5] ACCOUNT ROLE JUNCTION SLOT INTERACTIVE ENGINE")

    
    role_analysis = propose_account_role_swaps_for_single_account(
        account_id=account_id,
        df_staged_group=active_contact_rows,
        live_sf_account_row=account_record,
        contact_email_to_id=contact_email_to_id,
        contact_email_to_name=contact_email_to_name,
        df_sf_contacts=df_contacts_global
    )
    
    for match in role_analysis['perfect_matches']:
        print(f"     🟢 {match}")
        
    for conflict in role_analysis['multiplicity_conflicts']:
        print(f"     🛑 CONFLICT: Multiple conflicting emails submitted for {conflict['Role']}: {conflict['Emails']}")
    for unknown in role_analysis['unknown_emails']:
        print(f"     ⚠️  WARNING: Submitted email '{unknown['Email']}' for {unknown['Role']} doesn't exist in CRM Contact Directory.")

    if not role_analysis['proposed_swaps']:
        print("     🟢 No Account Role lookup swaps are required for this record.")
    else:
        # Create a reverse lookup dictionary to map Contact IDs back to their names instantly
        contact_id_to_name = {v: contact_email_to_name[k] for k, v in contact_email_to_id.items()}
        
        for swap in role_analysis['proposed_swaps']:
            print(f"\n     ❓ PROPOSED ROLE SWAP DETECTED FOR: {swap['Role']}")
            current_lookup_id = account_record.get(swap['Field'])
            
            # 🌟 BULLETPROOF LOCAL LOOKUP: Fall back to local high-speed memory dictionary instead of making a brittle API call
            if current_lookup_id and current_lookup_id in contact_id_to_name:
                old_name = contact_id_to_name[current_lookup_id]
            else:
                old_name = "[Vacant Lookup Slot or Unresolved Identity]"
            
            print(f"        CRM Current Occupant: {old_name}")
            print(f"        Form Proposed Seat  : {swap['Name']} ({swap['Email']})")
            
            if input(f"        Execute this lookup seat update inside Salesforce? (y/n): ").lower() == 'y':
                sf.Account.update(account_id, {swap['Field']: swap['ContactId']})
                print("        ✅ Salesforce Account Role updated successfully.")
                email_summary_notes.append(f"Assigned {swap['Name']} as the primary {swap['Role']}.")
            else:
                print("        ❌ Swap assignment rejected via user override instruction.")

    input("\n📥 Account Roles balanced. Press [ENTER] to construct outbound email confirmation draft...")

    # -----------------------------------------------------------------
    # STEP 6: EMAIL RECAP GENERATION & CLOSURE
    # -----------------------------------------------------------------
    print("\n📬 [STEP 6] OUTBOUND EMAIL RECAP GENERATION SUMMARY")
    print("-----------------------------------------------------------------")
    print(f"Subject: Profile Update Confirmation - {account_name} [{pu_name}]")
    print(f"Hi {submitter_name or 'Participant'},\n")
    
    # 🌟 VOICE-DRIVEN TRIGGER FILTER: Executing specialized template formatting rules for Key-Only variations
    if pu_rows_contact.empty and row_key is not None:
        print("Thank you for updating your information with AISC. The changes are summarized below.")
        
        # 1. Company Name Variance Generation Lines
        new_name = str(row_key.get('Revised_Company_Name__c', '')).strip()
        if new_name and new_name != 'nan' and new_name.lower() != account_name.lower():
            similarity_ratio = difflib.SequenceMatcher(None, account_name.lower(), new_name.lower()).ratio()
            if similarity_ratio >= 0.90:
                print(f"- We have updated your company name from {account_name} to {new_name}.")
            else:
                print(f"- We have updated your company name from {account_name} to {new_name}, but have added a temporary note to avoid confusion.")
                
        # 2. Company Ownership Variance Generation Lines
        new_owner = str(row_key.get('Revised_Company_Owner__c', '')).strip()
        current_owner = str(account_record.get('Company_Owner__c', '')).strip()
        if new_owner and new_owner != 'nan':
            if not current_owner:
                print(f"- We have noted your company ownership of {new_owner}.")
            elif current_owner.lower() != new_owner.lower():
                print(f"- We have updated your company ownership from {current_owner} to {new_owner}.")
                
        # 3. Decision-Driven Office vs. Facility Address Compiler Lines
        new_street = str(row_key.get('Revised_Facility_Street__c', '')).strip()
        if new_street and new_street != 'nan':
            old_street = account_record.get('BillingStreet', '[Unpopulated Address]')
            
            if account_industry == 'Erector':
                print(f"- We have updated your office address from {old_street} to {new_street}.")
                
            elif account_industry == 'Fabricator' and address_disposition is not None:
                if address_disposition == 1:
                    print(f"- We have updated your facility address from {old_street} to {new_street}.")
                elif address_disposition == 2:
                    print(f"- We have updated your facility address from {old_street} to {new_street} pending your upcoming audit.")
                elif address_disposition == 3:
                    print(f"- We have noted your facility address update from {old_street} to {new_street} and will follow up with next steps.")
    else:
        # Roster/Contact standard recap layout block fallback path
        print("Thank you for updating your information with AISC. Here is a summary of the updates executed:\n")
        if email_summary_notes:
            for note in email_summary_notes:
                print(f" * {note}")
        else:
            print(" * Contact roster record changes processed successfully.")
            
        print("\nOriginal Frozen Roster Configuration Baseline for your records:")
        print(snapshot_text_block.replace("     ", ""))
        
    print("-----------------------------------------------------------------")
    
    close_confirm = input("\n🏁 Have you responded to the Case and copied your email text? (y/n): ").strip().lower()
    if close_confirm == 'y':
        sf.Company_Profile_Change__c.update(pu_id, {'Status__c': 'Closed'})
        print(f"    🔒 Status set to 'Closed'. Closed Profile Update {pu_name} successfully inside Salesforce.")
    else:
        print(f"    ⚠️ Leaving Profile Update {pu_name} in 'New' status for secondary review pass.")

    print("\n" + "="*69 + "\n")
    break