import streamlit as st
import requests
from datetime import datetime, timedelta

# Read secrets
API_KEY = st.secrets["OPENROUTER_KEY"]
AZURE_ACCESS_TOKEN = st.secrets["AZURE_ACCESS_TOKEN"]
AZURE_SUBSCRIPTION_ID = st.secrets["AZURE_SUBSCRIPTION_ID"]
AZURE_RESOURCE_GROUP = st.secrets["AZURE_RESOURCE_GROUP"]
AZURE_VM_NAME = st.secrets["AZURE_VM_NAME"]

SNOW_INSTANCE = st.secrets["SNOW_INSTANCE"]
SNOW_USER = st.secrets["SNOW_USER"]
SNOW_PASSWORD = st.secrets["SNOW_PASSWORD"]

GITLAB_TOKEN = st.secrets["GITLAB_TOKEN"]
GITLAB_PROJECT_ID = st.secrets["GITLAB_PROJECT_ID"]

st.set_page_config(page_title="Unified AI", layout="centered")
st.title("🤖 Unified AI: Infra Assistant")

# ✅ Azure VM status
def get_azure_logs():
    try:
        vm_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines?api-version=2021-07-01"
        headers = {'Authorization': f"Bearer {AZURE_ACCESS_TOKEN}"}
        response = requests.get(vm_url, headers=headers)
        if response.status_code != 200:
            return f"Azure VM fetch error: {response.status_code}"

        data = response.json()
        results = []
        for vm in data['value']:
            name = vm['name']
            status_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{name}/instanceView?api-version=2021-07-01"
            status_response = requests.get(status_url, headers=headers)
            if status_response.status_code == 200:
                status = status_response.json()
                state = status['statuses'][1]['displayStatus']
                results.append(f"VM: {name}, Status: {state}")
        return "\n".join(results)
    except Exception as e:
        return f"Error: {e}"

# ✅ Azure Monitor metrics (CPU)
def get_vm_metrics():
    try:
        now = datetime.utcnow()
        start = (now - timedelta(minutes=30)).isoformat() + "Z"
        end = now.isoformat() + "Z"

        url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{AZURE_VM_NAME}/providers/microsoft.insights/metrics"
        params = {
            "api-version": "2018-01-01",
            "metricnames": "Percentage CPU",
            "timespan": f"{start}/{end}",
            "interval": "PT5M",
            "aggregation": "Average"
        }

        headers = {"Authorization": f"Bearer {AZURE_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return f"⚠️ CPU metric fetch failed: {response.status_code} - {response.text}"

        metrics = response.json().get("value", [])
        if not metrics:
            return "⚠️ No CPU metrics found."

        data = metrics[0]["timeseries"][0]["data"]
        values = [f"{d['timeStamp']} — CPU: {d.get('average', 0):.2f}%" for d in data if 'average' in d]
        return "\n".join(values)
    except Exception as e:
        return f"Error getting metrics: {e}"

# ✅ ServiceNow incidents
def get_incidents(query):
    try:
        url = f"{SNOW_INSTANCE}/api/now/table/incident?sysparm_query=short_description={query}&sysparm_limit=5"
        response = requests.get(url, auth=(SNOW_USER, SNOW_PASSWORD))
        if response.status_code != 200:
            return f"ServiceNow error: {response.status_code}"
        data = response.json().get("result", [])
        if not data:
            return "No incidents found."
        return "\n".join([f"{i['short_description']} — State: {i['state']}" for i in data])
    except Exception as e:
        return f"SNOW Error: {e}"

# ✅ GitLab pipeline status
def get_pipeline_info():
    try:
        url = f"https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/pipelines"
        headers = {'Private-Token': GITLAB_TOKEN}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return f"GitLab error: {response.status_code}"
        data = response.json()
        if not data:
            return "No pipelines found."
        latest = data[0]
        return f"Pipeline #{latest['id']} — Status: {latest['status']}"
    except Exception as e:
        return f"GitLab error: {e}"

# ✅ Prompt builder
def create_prompt(query, azure_logs, metrics, snow, gitlab):
    return f"""
Customer Query: {query}

--- Azure VM Status ---
{azure_logs}

--- Azure VM Metrics ---
{metrics}

--- ServiceNow Tickets ---
{snow}

--- GitLab Pipelines ---
{gitlab}

As an infrastructure assistant, summarize key issues and provide specific next steps.
"""

# ✅ LLM call
def ask_openrouter(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "anthropic/claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"LLM error: {e}"

# ✅ Streamlit UI
query = st.text_input("Enter your customer issue/query:")

if query:
    with st.spinner("Analyzing infrastructure..."):
        azure = get_azure_logs()
        metrics = get_vm_metrics()
        snow = get_incidents(query)
        gitlab = get_pipeline_info()
        prompt = create_prompt(query, azure, metrics, snow, gitlab)
        response = ask_openrouter(prompt)

    st.success("Unified AI Response:")
    st.markdown(response)
