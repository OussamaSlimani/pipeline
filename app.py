from flask import Flask, render_template
import requests
import time
import json
import base64
import os
import threading

app = Flask(__name__)

# Configuration
API_URL = "https://api.us.cloud.talend.com/orchestration/artifacts"
API_KEY = "42wUMH3ASRuBMIpax-2qCiU11yI9NE2xdUHfDGuYcwewF3G6rccIT1Yigypo88H1"
AZURE_ORG = "OS-TAL-S3"
AZURE_PROJECT = "AutomateBusiness Process"
AZURE_PIPELINE_ID = "2"
AZURE_API_URL = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/pipelines/{AZURE_PIPELINE_ID}/runs?api-version=7.1-preview.1"
AZURE_PAT = "7f3hq2LLhZIxrOMICeckIGJb4xfH2vdC9Zx6laUr4kZSiUkC7epBJQQJ99BCACAAAAA3rlxtAAASAZDO4ZNW"
STATE_FILE = "previous_artifacts.json"

# Global variables to store monitoring status and logs
monitoring_status = "Stopped"
log_entries = []
last_trigger_time = None

def trigger_azure_pipeline():
    global last_trigger_time
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode((':' + AZURE_PAT).encode()).decode()}"
    }
    payload = json.dumps({
        "stagesToSkip": [],
        "resources": {
            "repositories": {
                "self": {
                    "refName": "refs/heads/main"
                }
            }
        }
    })

    try:
        response = requests.post(AZURE_API_URL, headers=headers, data=payload)
        response.raise_for_status()
        log_message = "✅ Pipeline Azure DevOps déclenchée avec succès !"
        print(log_message)
        log_entries.append(log_message)
        last_trigger_time = time.strftime("%Y-%m-%d %H:%M:%S")
    except requests.exceptions.RequestException as e:
        log_message = f"❌ Erreur lors du déclenchement de la pipeline : {e}"
        print(log_message)
        log_entries.append(log_message)

def fetch_artifacts():
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()
        return response.json().get('items', [])
    except requests.exceptions.RequestException as e:
        log_message = f"Error while fetching artifacts: {e}"
        print(log_message)
        log_entries.append(log_message)
        return None

def load_previous_artifacts():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_current_artifacts(current_artifacts):
    with open(STATE_FILE, 'w') as file:
        json.dump(current_artifacts, file)

def monitor_artifacts():
    global monitoring_status
    previous_artifacts = load_previous_artifacts()
    first_run = len(previous_artifacts) == 0

    monitoring_status = "Running"
    log_message = "Starting artifact monitoring..."
    print(log_message)
    log_entries.append(log_message)

    while monitoring_status == "Running":
        current_artifacts = fetch_artifacts()
        
        if current_artifacts is not None:
            current_artifacts_data = {artifact['id']: artifact for artifact in current_artifacts}
            trigger_pipeline_flag = False
            
            for artifact_id, artifact in current_artifacts_data.items():
                artifact_name = artifact['name']
                artifact_versions = set(artifact['versions'])
                
                if artifact_id not in previous_artifacts:
                    log_message = f"New artifact published: {artifact_name} (ID: {artifact_id})"
                    print(log_message)
                    log_entries.append(log_message)
                    trigger_pipeline_flag = True
                else:
                    previous_versions = set(previous_artifacts[artifact_id]['versions'])
                    new_versions = artifact_versions - previous_versions
                    
                    if new_versions:
                        log_message = f"New versions published for {artifact_name} (ID: {artifact_id}): {', '.join(new_versions)}"
                        print(log_message)
                        log_entries.append(log_message)
                        trigger_pipeline_flag = True
                
                previous_artifacts[artifact_id] = {
                    'name': artifact_name,
                    'versions': list(artifact_versions)
                }
            
            if trigger_pipeline_flag and not first_run:
                trigger_azure_pipeline()
            
            save_current_artifacts(previous_artifacts)
            first_run = False
        
        time.sleep(30)

    log_message = "Artifact monitoring stopped."
    print(log_message)
    log_entries.append(log_message)

@app.route('/')
def index():
    return render_template('index.html', 
                         status=monitoring_status,
                         logs=log_entries[-10:],  # Show last 10 log entries
                         last_trigger=last_trigger_time)

@app.route('/start')
def start_monitoring():
    global monitoring_thread
    if monitoring_status != "Running":
        monitoring_thread = threading.Thread(target=monitor_artifacts)
        monitoring_thread.daemon = True
        monitoring_thread.start()
    return index()

@app.route('/stop')
def stop_monitoring():
    global monitoring_status
    monitoring_status = "Stopped"
    return index()

if __name__ == '__main__':
    app.run(debug=True)