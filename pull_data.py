import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

# 1. Connect
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# 2. Define your SOQL Query (The "Input" step)
# Let's grab some Accounts as a test
query = "SELECT Name, Industry, Phone, BillingState FROM Account LIMIT 10"

# 3. Execute and convert to a list of dictionaries
results = sf.query_all(query)
records = results['records']

# 4. Convert to a DataFrame (The "Tableau Prep" Workspace)
# We drop the 'attributes' column because Salesforce adds metadata we don't need
df = pd.DataFrame(records).drop(columns='attributes')

# 5. Preview the data
print("--- Data Preview ---")
print(df.head())

# 6. Save to CSV (The "Output" step)
df.to_csv('salesforce_accounts.csv', index=False)
print("\n✅ File 'salesforce_accounts.csv' has been created!")