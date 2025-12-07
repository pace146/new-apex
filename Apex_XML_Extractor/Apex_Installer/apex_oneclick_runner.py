import os, json, subprocess, datetime, sys

CONFIG_FILE = 'Apex_Config.json'

def log(msg):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    print(line)
    with open(os.path.join(config['log_folder'], f'apex_log_{today}.txt'), 'a') as f:
        f.write(line + '\n')

def run_script(script_name):
    log(f'Running: {script_name}')
    try:
        subprocess.check_call(['python', script_name])
        log(f'SUCCESS: {script_name}')
    except subprocess.CalledProcessError as e:
        log(f'ERROR while running {script_name}: {e}')
        sys.exit(1)

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

today = datetime.datetime.now().strftime('%Y%m%d')

for d in [config['log_folder'], config['report_folder'], config['utf_output_folder']]:
    if not os.path.exists(d):
        os.makedirs(d)

log('=== APEX ONE-CLICK RUNNER STARTED ===')

run_script(config['extractor_script'])
run_script(config['cleaner_script'])

if config['live_odds_enabled']:
    run_script(config['live_odds_script'])
else:
    log('Live odds disabled — skipping')

run_script(config['mc_verticals_script'])
run_script(config['horizontal_script'])
run_script(config['utf_builder_script'])

log('=== APEX PROCESS COMPLETE ===')
