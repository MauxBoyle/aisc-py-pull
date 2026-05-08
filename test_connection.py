import os
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

user = os.getenv('SF_USERNAME')
pw = os.getenv('SF_PASSWORD')
token = os.getenv('SF_TOKEN')

# Troubleshooting prints
print(f"DEBUG: Username loaded: {user}")
print(f"DEBUG: Password starts with: {pw[:2] if pw else 'MISSING'}")
print(f"DEBUG: Token starts with: {token[:2] if token else 'MISSING'}")

try:
    sf = Salesforce(username=user, password=pw, security_token=token)
    print(f"✅ Success! Connected to: {sf.sf_instance}")
except Exception as e:
    print(f"❌ Connection Failed: {e}")