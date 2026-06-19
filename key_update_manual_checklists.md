# 🔑 [STEP 4.5] INTERACTIVE KEY DATA RECONCILIATION COCKPIT

## 📡 CURRENT CRM AUDIT & STATE CONTEXT
* Upcoming Scheduled Audit? [FETCH LIVE: Audit_Date__c / Status]
* No Upcoming Audit? Last Audit completed on: [FETCH LIVE: Last_Audit_Date__c]
* Recent Case Activity (Last 6 Months): [Review displayed Case Stack]

---

## 🏗️ TYPE 1: OWNERSHIP MODIFICATION LAYER
### Operational Logic:
* If current CRM Account field is [Blank], queue simple insertion payload.
* If current CRM Account field has an active value, queue historical swap payload.

### 📬 Target Email Summary Snippets:
* Standard Insertion: "Your company ownership of {New Ownership} was noted."
* Standard Replacement: "Your company ownership was updated from {Old Ownership} to {New Ownership}."

---

## 🔤 TYPE 2: COMPANY NAME RECONCILIATION LAYER
### Operational Logic:
* [PROGRAMMATIC] Run Levenshtein Distance Check on {Old Name} vs {New Name}.
* IF Similarity >= 90% (e.g., Inc. to LLC): Classify as **Simple Name Change**. Approve on copy-paste recap.
* IF Similarity < 90% (Significant structural rebranding):
    1. Update Salesforce Account Name string field format to: `{New Name} (f.k.a. {Old Name})`
    2. Create a high-priority **Salesforce Task** assigned to yourself: 
       * *Subject:* "Remove f.k.a. structural suffix after successful completion of next Audit cycle."
       * *Due Date:* Set to 7 days post-Upcoming Audit Date.

---

## 🗺️ TYPE 3: ADDRESS MODIFICATION LAYER (THE RISK MATRIX)

### ⚙️ CRITERIA A: Account Industry == 'Erector' (Low Risk)
* Action: **AUTOMATICALLY APPROVE**. Update all core Account address fields instantly.
* Audit Boundary Intercept: 
    * If there is an **Upcoming Audit** on file, automatically spawn a **Salesforce Task** assigned to yourself:
      * *Subject:* "MANUAL CHATTER TAG: Notify current Auditor Liaison regarding Erector facility address relocation."
      *(Note: We will manually tag the liaison on the Case feed since automated mentions require explicit user loops).*

### 🧪 CRITERIA B: Account Industry == 'Fabricator' (HIGH RISK - MANUAL REVIEW)
* Action: **FORCE MANUAL COCKPIT SUSPENSION**. Do not auto-approve.
* Data Visual Additions for Review Screen:
    * 📍 Display Google Maps API Geodesic Distance Matrix result: `[Calculate Physical Distance: Old Lat/Long vs New Lat/Long]`
* CRM Record Safe-State Staging:
    * Update the Account Address fields immediately to reflect the physical reality, but preface the main address block with this text: 
      `(pending address update) {New Street Address}`
* High-Risk Penalty Assessment Options:
    * Option 1: Proceed with standard review if distance is minimal.
    * Option 2: Flag Account for Certification Discontinuation process.
    * Option 3: Force-trigger a special, immediate intermediate Facility Audit.