# 🗺️ Project Log & Automation Roadmap

**File Name:** `DESIGN_NOTES.md` / `ROADMAP.md`  
**Current State:** Submissions are cleanly staged into two localized files (`staged_key_updates.csv` and `staged_contact_updates.csv`). Standard case generation, internal text-block routing, and active Title backfill automations are fully baseline operational.

---

## 🚀 Active Roadmap & Future Improvements

### 1. Staging Layer Data Cleaners (Pre-Processing)
* **Title Spell-Check & Dictionary Standardization:** Intercept common corporate typos at the form submission level before they touch the evaluation engine. 
    * *Example caught in production:* `Chief Ficial Officer` ➡️ Auto-correct to `Chief Financial Officer`.
* **Role-Based "Email-Only" Vector Routing:** Expand horizontal backfill rules so that if a participant submits *only* an email address for a role, the script dynamically hunts the live Salesforce cache by email to backfill the missing First Name, Last Name, Title, and Phone parameters into the staging table.

### 2. Contact Reconciliation Heuristics (Comparison Layer)
* **Name Squashing (First + Middle Extensions):** Resolve false-positive name mismatches caused by middle names or initials stored natively inside Salesforce's `FirstName` field (or separate `MiddleName` API field) when a participant submits a combined string.
    * *Example caught in production:* Salesforce `FirstName` is `Jo` (with `Ann` in Middle Name or squashed), but participant submits `Jo Ann`. Implement a `.startswith()` prefix comparison test to auto-clear.
* **Salesforce Required Field Enforcement:** Ensure the system respects target schema validation requirements for net-new entries before generating Data Loader or direct API writing payloads.
    * *The "LastName" Requirement Rule:* Salesforce strictly requires a `LastName` for all Contacts. If a submission contains an anonymous role-based placeholder (e.g., `FirstName: Accounting`, `LastName: [Blank]`), the engine must auto-shift the data: `LastName = FirstName` and `FirstName = ""`.

### 3. Identity Resolution Architecture (Long-Term Value)
* **Email Heuristic Classification:** Differentiate between personal inbox addresses and corporate role/seat aliases to safely protect CRM data history.
    * *Personal Identifiers (`firstname.lastname@`):* High persistence accuracy. If names mismatch completely on an existing email, flag for a strict typo/spelling audit.
    * *Role/Seat Identifiers (`accounting@`, `qa@`, `purchasing@`):* High employee turnover probability. If a completely new name claims a role-based inbox address, interpret this as a *job transition* rather than a typo. Auto-archive the historical contact record and spawn a fresh, clean record for the new corporate seat-holder to protect historical data integrity.

---

## 🛠️ Current Operational Pipeline Summary

```text
    [Participant Portal Submissions]
                   │
                   ▼
       stage_profile_updates.py
    ┌──────────────┴──────────────┐
    ▼                             ▼
staged_key_updates.csv     staged_contact_updates.csv
(Facility & Narratives)    (Sanitized Roster Data)
    │                             │
    ▼                             ▼
generate_profile_cases_pu.py     update_contact_records.py
(Cuts Core Cases & Feeds)  (Auto-Patches Blank Titles)
                                  │
                                  ▼
                             [Data Loader Engine]
                             net_new_contacts.csv

Staging State: Phone tracking fields universally formatted to clean dot-notation (312.555.1234). All floating point NaN structural artifacts recursively scrubbed and normalized to clean empty space blocks ("").

Case Generation State: Outputs high-visibility minute-precision system runtime headers (🚨 PROFILE UPDATE PU-XXXXX RECEIVED YYYY-MM-DD HH:MM 🚨) into internal case comments alongside comma-delimited contact lists.

Reconciliation State: Consolidates multiple submissions to single-email instances. Matches numbers seamlessly via a country-code-stripping digit normalizer. Directly automates live writes back into Salesforce for records containing unique title updates against a blank baseline. Silences net-new logs and groups true additions into a separate Data Loader pipeline.

Log updated as of June 2026.

### 4. Automated Post-Update Email Engine (Snapshot-in-Time Pattern)
* **The State Drift Problem:** Because Contact cleaning and Account Role updates happen sequentially, the live CRM database changes before the notification engine can compile a "Before vs. After" comparison summary for the participant.
* **The Solution Architecture:** Build a dedicated execution module (`compile_email_payloads.py`) that runs *at the absolute beginning of the pipeline*, immediately after `stage_profile_updates.py` finishes.

#### The Three-Layer Email Data Object (JSON or CSV Buffer):
For every processed Account, the pipeline will capture and freeze this snapshot data to disk:
1. **Metadata Block:** Submitter Name, Submitter Email, Account Name, Certification ID.
2. **The "Before" Snapshot:** Reads the live, untouched Salesforce Account Role fields and grabs the exact names/emails currently occupying those slots.
3. **The "After" Snapshot:** Copies your pristine, dot-formatted `staged_contact_updates.csv` parameters.

#### The Automation Loop Execution Flow:
```text
  [Staged Data Ready] ➡️ [Freeze "Before" Snapshot] ➡️ [Execute CRM Writes] ➡️ [Inject Frozen Delta into Email Template]

  ## 🕵️‍♂️ Edge Cases & System Observations (June 2026 Batch)

* **Profile Expected Lookback Extension:** Expand the Profile Expected query logic window beyond 30 days (potentially to 60 or 90 days) to prevent slower-moving validation cycles from clipping historical context.
* **Duplicate Case Generation Fault:** Investigate `generate_profile_cases_pu.py` for a race condition where a single Profile Update record spawns two distinct Salesforce Cases. Implement a stricter pre-creation check against the live CRM and local history file.
* **Roster Monopolization Flag:** Add an auditing rule to flag submissions where all 4 contact roles are occupied by the exact same email address. This indicates an operational single point of failure or lazy form submission behavior.
* **Ownership vs. Ownership Owner Field Redundancy:** Audit Table A text-block generation logic to determine why both `Ownership` and `Ownership Owner` are being extracted into the narrative block, and streamline how these schema values co-exist.

