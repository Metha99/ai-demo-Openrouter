import streamlit as st
import requests
import re

# Streamlit secrets (store securely at Settings > Secrets)
API_KEY = st.secrets["OPENROUTER_KEY"]

AZURE_ACCESS_TOKEN = st.secrets["AZURE_ACCESS_TOKEN"]
AZURE_SUBSCRIPTION_ID = "unified-ai-demo"
AZURE_RESOURCE_GROUP = "unified-ai-prototype"

SNOW_INSTANCE = st.secrets["SNOW_INSTANCE"]
SNOW_USER = st.secrets["SNOW_USER"]
SNOW_PASSWORD = st.secrets["SNOW_PASSWORD"]

GITLAB_TOKEN = st.secrets["GITLAB_TOKEN"]
GITLAB_PROJECT_ID = "12345678"  # Replace with your actual project ID

st.set_page_config(page_title="Unified AI", layout="centered")
st.title("🤖 Unified AI: Infra Assistant")

# ✅ Azure logs
def get_azure_logs(query):
    vm_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines?api-version=2021-07-01"
    headers = {'Authorization': f"Bearer {AZURE_ACCESS_TOKEN}"}
    response = requests.get(vm_url, headers=headers)

    if response.status_code != 200:
        return f"Error fetching Azure VMs. Status: {response.status_code}, Details: {response.text}"

    vm_data = response.json()
    vm_statuses = []
    for vm in vm_data.get('value', []):
        vm_name = vm['name']
        status_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{vm_name}/instanceView?api-version=2021-07-01"
        status_response = requests.get(status_url, headers=headers)
        if status_response.status_code == 200:
            vm_status = status_response.json()
            try:
                status = vm_status['statuses'][1]['displayStatus']
                vm_statuses.append(f"VM: {vm_name} - Status: {status}")
            except Exception as e:
                vm_statuses.append(f"VM: {vm_name} - Status unknown: {e}")
        else:
            vm_statuses.append(f"VM: {vm_name} - Failed to fetch status. Code: {status_response.status_code}")
    return "\n".join(vm_statuses)


# ✅ GitLab: Parse pipeline ID from user input
def get_pipeline_info(query):
    match = re.search(r"#?(\d{6,})", query)
    if match:
        pipeline_id = match.group(1)
    else:
        return "No valid pipeline ID found in query."

    gitlab_url = f"https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/pipelines/{pipeline_id}"
    headers = {'Private-Token': GITLAB_TOKEN}
    response = requests.get(gitlab_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        status = data.get('status', 'Unknown')
        ref = data.get('ref', 'N/A')
        return f"Pipeline #{pipeline_id} on branch `{ref}` has status: {status}"
    else:
        return f"GitLab pipeline fetch error {response.status_code}: {response.text}"


# ✅ SNOW with debugging
def get_incidents(query):
    url = f"{SNOW_INSTANCE}/api/now/table/incident?sysparm_query=short_description={query}&sysparm_limit=5"
    auth = (SNOW_USER, SNOW_PASSWORD)
    response = requests.get(url, auth=auth)

    if response.status_code != 200:
        return f"Error fetching ServiceNow data. Code: {response.status_code}, Details: {response.text}"

    try:
        incidents = response.json()['result']
        if not incidents:
            return "No incidents found."
        return "\n".join([f"Incident: {i.get('short_description')} - Status: {i.get('state')}" for i in incidents])
    except Exception as e:
        return f"ServiceNow parse error: {e}"


# ✅ Prompt builder
def create_prompt(query, azure_data, servicenow_data, gitlab_data):
    return f"""
You are an intelligent assistant analyzing customer infrastructure.

Customer Query: {query}

--- Azure Resources ---
{azure_data}

--- ServiceNow Tickets ---
{servicenow_data}

--- GitLab Pipelines ---
{gitlab_data}

Provide a summary and actionable insights.
"""


# ✅ OpenRouter API (Claude 3 Sonnet)
def ask_openrouter(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "anthropic/claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Error communicating with OpenRouter: {e}"


# ✅ UI input
query = st.text_input("Enter your customer issue/query:")

if query:
    with st.spinner("Analyzing data sources..."):
        azure = get_azure_logs(query)
        snow = get_incidents(query)
        gitlab = get_pipeline_info(query)
        final_prompt = create_prompt(query, azure, snow, gitlab)
        response = ask_openrouter(final_prompt)

    st.success("Unified AI Response:")
    st.markdown(response)
