import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

# --- STEP 1: CONNECTION ---
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

def get_df(soql):
    """Helper to pull Salesforce data into a DataFrame"""
    results = sf.query_all(soql)
    return pd.DataFrame(results['records']).drop(columns='attributes', errors='ignore')

print("🚀 Extracting data from Salesforce...")

# --- STEP 2: EXTRACTION & RENAMING (The "Input" steps) ---

# Account
df_account = get_df("""
    SELECT Id, Name, BillingCountry, Industry, NumberOfEmployees, CreatedDate, 
    Certification_ID__c, Cert_Audit_Package__c, Is_active_in_IMIS_for_Member_Discount__c, 
    Cert_Certification_Status__c, Cert_Scheduling_2_0_Cert_Month__c 
    FROM Account
""")

df_account = df_account.rename(columns={
    'Id': 'Account_18dan', 
    'Name': 'Account_Name', 
    'Certification_ID__c': 'Certification_ID',
    'Cert_Audit_Package__c': 'Audit_Pkg18dan', 
    'Cert_Scheduling_2_0_Cert_Month__c': 'Sched2Month',
    'Cert_Certification_Status__c': 'Cert_Certification_St' # Matching your Tableau logic
})

# Audit Package
df_pkg = get_df("SELECT Id, Name, LastModifiedDate, Cert_Active__c FROM Cert_Audit_Package__c")
df_pkg = df_pkg.rename(columns={'Id': 'Package_18dan', 'Name': 'AuditPackage'})

# Certification
df_cert = get_df("SELECT Id, Name, Cert_Account__c, Cert_Certification_Type__c, End_Date__c, Start_Date__c, Status__c FROM Cert_Certification__c")
df_cert = df_cert.rename(columns={
    'Id': 'Certification_18dan', 'Name': 'Certification', 'Cert_Account__c': 'Certification_Acct18dan',
    'Cert_Certification_Type__c': 'Certification_Type', 'End_Date__c': 'Certification_EndDate', 'Status__c': 'Certification_Status'
})

# Audit
df_audit = get_df("SELECT Id, Name, Cert_Account__c, Cert_Audit_Date__c, Cert_Audit_Scope__c, Cert_Audit_Status__c, Cert_Audit_Type__c, Additional_Audit__c FROM Cert_Audit__c")
df_audit = df_audit.rename(columns={
    'Id': 'Audit_18dan', 'Name': 'Audit_Number', 'Cert_Account__c': 'Audit_Acct18dan',
    'Cert_Audit_Scope__c': 'Audit_Scope', 'Cert_Audit_Type__c': 'Audit_Type'
})

# Audit Review
df_review = get_df("SELECT Id, Name, Cert_Account__c, Cert_Audit__c, Is_a_B_Audit_Needed__c, Cert_AISC_Outcome__c, Cert_CRG_Outcome__c, AISC_Comments__c, CRG_Comments__c FROM Cert_Audit_Review__c")
df_review = df_review.rename(columns={
    'Id': 'AR_18dan', 'Cert_Audit__c': 'AR_Audit18dan', 'Cert_CRG_Outcome__c': 'CRG_Outcome'
})

# --- STEP 3: THE JOINS (The "Everything" Step) ---
print("🔗 Merging tables...")

# Join 5: Account + Audit Package
join_5 = pd.merge(df_account, df_pkg, left_on='Audit_Pkg18dan', right_on='Package_18dan', how='inner')

# AcctWCerts: Join 5 + Certification
acct_w_certs = pd.merge(df_cert, join_5, left_on='Certification_Acct18dan', right_on='Account_18dan', how='inner')

# ReviewedAudit: Audit + Audit Review
reviewed_audit = pd.merge(df_audit, df_review, left_on='Audit_18dan', right_on='AR_Audit18dan', how='inner')

# EVERYTHING: AcctWCerts + ReviewedAudit
everything = pd.merge(acct_w_certs, reviewed_audit, left_on='Account_18dan', right_on='Audit_Acct18dan', how='inner')

# --- STEP 4: FILTERING & CALCULATIONS (The "GreenFolder" Step) ---
print("🧹 Filtering and calculating fields...")

gf = everything.copy()

# Filters
gf = gf[gf['CRG_Outcome'] == "Certification Recommended"]
gf = gf[~gf['Audit_Scope'].str.contains("NY", na=False)]
gf = gf[gf['Audit_Scope'] != "RFN"]
gf = gf[~gf['Account_Name'].str.contains("onditional", na=False)]
gf = gf[gf['Audit_Type'] != "Initial"]
gf = gf[gf['Certification_Status'] != "Inactive"]

# Calculated Field: Expy Est Error
# Logic: We need to parse the AuditPackage (e.g. "05 - May") to get the week number
def calculate_expy_error(row):
    try:
        # Convert dates to pandas datetime objects
        sched_month = pd.to_datetime(row['Sched2Month'])
        today = datetime.now()
        this_year = today.year
        
        # Extract week number from "AuditPackage" (first 2 chars)
        week_num = int(row['AuditPackage'][:2])
        
        # Calculate base date for this year
        base_date = datetime(this_year, 1, 1) + timedelta(weeks=week_num)
        
        # Tableau Logic: If base date is in future, use last year
        if base_date > today:
            base_date = datetime(this_year - 1, 1, 1) + timedelta(weeks=week_num)
        
        # Add 3 months
        calc_date = base_date + pd.DateOffset(months=3)
        
        # Return Absolute difference in months (approximate)
        return abs((sched_month.year - calc_date.year) * 12 + (sched_month.month - calc_date.month))
    except:
        return np.nan

gf['Expy Est Error'] = gf.apply(calculate_expy_error, axis=1)

# Calculated Field: ExpyMatch
gf['Certification_EndDate'] = pd.to_datetime(gf['Certification_EndDate'])
gf['Sched2Month'] = pd.to_datetime(gf['Sched2Month'])
gf['ExpyMatch'] = gf['Sched2Month'].dt.month == gf['Certification_EndDate'].dt.month

# Final Cleanup: Remove fields
gf = gf.drop(columns=['Package_18dan', 'Audit_Pkg18dan'], errors='ignore')

# --- STEP 5: OUTPUT ---
gf.to_csv('GreenFolder_Output.csv', index=False)
print(f"✅ GreenFolder complete! {len(gf)} records processed.")