import os, json, subprocess, datetime, sys

CONFIG_FILE = "Apex_Config.json"

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(os.path.join(config["log_folder"], f"apex_log_{today}.txt"), "a") as f:
        f.write(line + "\n")

def run_script(script_name):
    log(f"Running: {script_name}")
    try:
        subprocess.check_call(["python", script_name])
        log(f"SUCCESS: {script_name}")
    except subprocess.CalledProcessError as e:
        log(f"ERROR while running {script_name}: {e}")
        sys.exit(1)

# -------------------------------------------------------------

# Load config
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

today = datetime.datetime.now().strftime("%Y%m%d")

# Ensure directories exist
for d in [config["log_folder"], config["report_folder"], config["utf_output_folder"]]:
    if not os.path.exists(d):
        os.makedirs(d)

log("=== APEX ONE-CLICK CARD RUNNER STARTED ===")

# Step 1: XML extract
run_script(config["extractor_script"])

# Step 2: CPR Cleaner
run_script(config["cleaner_script"])

# Step 3: Live odds (optional)
if config["live_odds_enabled"]:
    run_script(config["live_odds_script"])
else:
    log("Live odds disabled — skipping")

# Step 4: Ultra Monte Carlo vertical builder
run_script(config["mc_verticals_script"])

# Step 5: Horizontal ticket builder
run_script(config["horizontal_script"])

# Step 6: UTF slip builder (vertical + horizontal + WP)
run_script(config["utf_builder_script"])

log("=== APEX CARD PROCESSING COMPLETE ===")
