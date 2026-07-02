import os
import sys
import subprocess
from datetime import datetime

# Get the absolute directory path where this orchestrator script lives
# This ensures Task Scheduler doesn't get lost finding your files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define your pipeline files in their exact required execution order
PIPELINE_SCRIPTS = [
    "generate_profile_cases_audit.py",
    "stage_profile_updates.py",
    "generate_profile_cases_pu.py"
]

def run_pipeline():
    start_time = datetime.now()
    print(f"=====================================================================")
    print(f"🚀 STARTING AISC DAILY AUTOMATION PIPELINE: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=====================================================================\n")

    # Force change Python's working directory to your project folder
    os.chdir(BASE_DIR)

    # Use the active virtual environment's Python executable to prevent library path bugs
    python_executable = sys.executable

    for script in PIPELINE_SCRIPTS:
        script_path = os.path.join(BASE_DIR, script)
        
        if not os.path.exists(script_path):
            print(f"❌ CRITICAL CONFIGURATION ERROR: '{script}' not found at {script_path}")
            print("🛑 Pipeline execution aborted.")
            sys.exit(1)

        print(f"🏃 Running Module: {script} ...")
        
        # Execute the script, letting its output print directly to your terminal screen
        result = subprocess.run([python_executable, script_path])
        
        # Check if the module crashed or threw an unhandled exception
        if result.returncode != 0:
            print(f"\n❌ CRITICAL CRASH IN MODULE: '{script}' failed with exit code {result.returncode}.")
            print("🛑 Pipeline execution halted immediately to prevent downstream state corruption.")
            sys.exit(result.returncode)
            
        print(f"✅ Module '{script}' finished successfully.\n")

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"=====================================================================")
    print(f"🎉 PIPELINE EXECUTION COMPLETE")
    print(f"⏱️ Total Runtime Duration: {duration}")
    print(f"=====================================================================")

if __name__ == "__main__":
    run_pipeline()