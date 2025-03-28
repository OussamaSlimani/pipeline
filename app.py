from flask import Flask, jsonify
import requests
import time
import json
import base64
import os
import threading

# Flask app
app = Flask(__name__)

# Talend API
API_URL = "https://api.us.cloud.talend.com/orchestration/artifacts"
API_KEY = "42wUMH3ASRuBMIpax-2qCiU11yI9NE2xdUHfDGuYcwewF3G6rccIT1Yigypo88H1"

# Azure DevOps API
AZURE_ORG = "OS-TAL-S3"
AZURE_PROJECT = "AutomateBusiness Process"
AZURE_PIPELINE_ID = "2"
AZURE_API_URL = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/pipelines/{AZURE_PIPELINE_ID}/runs?api-version=7.1-preview.1"
AZURE_PAT = "7f3hq2LLhZIxrOMICeckIGJb4xfH2vdC9Zx6laUr4kZSiUkC7epBJQQJ99BCACAAAAA3rlxtAAASAZDO4ZNW"

# Function to trigger Azure pipeline
def trigger_azure_pipeline():
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
        print("✅ Pipeline Azure DevOps triggered successfully!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error triggering Azure pipeline: {e}")

# File to store the previous state of artifacts and versions
STATE_FILE = "previous_artifacts.json"

# Function to fetch the list of artifacts
def fetch_artifacts():
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data.get('items', [])
    except requests.exceptions.RequestException as e:
        print(f"Error while fetching artifacts: {e}")
        return None

# Load the previously processed artifacts from a file (if any)
def load_previous_artifacts():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save the current artifacts to a file
def save_current_artifacts(current_artifacts):
    with open(STATE_FILE, 'w') as file:
        json.dump(current_artifacts, file)

# Function to monitor artifacts and detect new artifacts or new versions
def monitor_artifacts():
    previous_artifacts = load_previous_artifacts()
    first_run = len(previous_artifacts) == 0  # Check if this is the first run (no previous data)

    while True:
        current_artifacts = fetch_artifacts()
        
        if current_artifacts is not None:
            current_artifacts_data = {artifact['id']: artifact for artifact in current_artifacts}
            trigger_pipeline_flag = False
            
            for artifact_id, artifact in current_artifacts_data.items():
                artifact_name = artifact['name']
                artifact_versions = set(artifact['versions'])
                
                if artifact_id not in previous_artifacts:
                    print(f"New artifact published: {artifact_name} (ID: {artifact_id})")
                    trigger_pipeline_flag = True
                else:
                    previous_versions = set(previous_artifacts[artifact_id]['versions'])
                    new_versions = artifact_versions - previous_versions
                    
                    if new_versions:
                        print(f"New versions published for {artifact_name} (ID: {artifact_id}): {', '.join(new_versions)}")
                        trigger_pipeline_flag = True
                
                previous_artifacts[artifact_id] = {
                    'name': artifact_name,
                    'versions': list(artifact_versions)
                }
            
            if trigger_pipeline_flag and not first_run:
                trigger_azure_pipeline()
                
            save_current_artifacts(previous_artifacts)
        
        time.sleep(30)

# Flask route to start artifact monitoring in a separate thread
@app.route('/start_monitoring', methods=['GET'])
def start_monitoring():
    # Run monitoring in a separate thread to not block the Flask server
    monitoring_thread = threading.Thread(target=monitor_artifacts)
    monitoring_thread.daemon = True
    monitoring_thread.start()

    return jsonify({"message": "Artifact monitoring started!"})

if __name__ == "__main__":
    app.run(debug=True)
