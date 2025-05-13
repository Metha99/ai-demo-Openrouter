# ✅ REWRITTEN FOR OPENROUTER (FREE LLM)
# Fully replaces OpenAI with OpenRouter API (compatible with Mistral, LLaMA, etc.)
# Step-by-step deployment instructions follow below this code.

import streamlit as st
import requests

# 🔐 Read your OpenRouter API key securely from Streamlit secrets
API_KEY = st.secrets["OPENROUTER_KEY"]

# Azure, SNOW, GitLab setup — unchanged
AZURE_ACCESS_TOKEN = st.secrets["AZURE_ACCESS_TOKEN"]
AZURE_SUBSCRIPTION_ID = "unified-ai-demo"
AZURE_RESOURCE_GROUP = "unified-ai-prototype"

SNOW_INSTANCE = "https://dev203611.service-now.com"
SNOW_USER = "admin"
SNOW_PASSWORD = "Nachet@123$$$$$$"

GITLAB_TOKEN = st.secrets["GITLAB_TOKEN"]
GITLAB_PROJECT_ID = "12345678"

st.set_page_config(page_title="Unified AI", layout="centered")
st.title("🤖 Unified AI: Infra Assistant")

# Azure Logs

def get_azure_logs(query):
    vm_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines?api-version=2021-07-01"
    headers = {'Authorization': f"Bearer {AZURE_ACCESS_TOKEN}"}

    response = requests.get(vm_url, headers=headers)
    if response.status_code == 200:
        vm_data = response.json()
        vm_statuses = []
        for vm in vm_data['value']:
            vm_name = vm['name']
            status_url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{vm_name}/instanceView?api-version=2021-07-01"
            status_response = requests.get(status_url, headers=headers)
            if status_response.status_code == 200:
                vm_status = status_response.json()
                status = vm_status['statuses'][1]['displayStatus']
                vm_statuses.append(f"VM Name: {vm_name}, Status: {status}")
        return "\n".join(vm_statuses)
    else:
        return f"Error fetching Azure VMs. Status code: {response.status_code}"


# GitLab

def get_pipeline_info(query):
    gitlab_url = f"https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/pipelines"
    headers = {'Private-Token': GITLAB_TOKEN}
    response = requests.get(gitlab_url, headers=headers)
    if response.status_code == 200:
        pipelines = response.json()
        if pipelines:
            last_pipeline = pipelines[0]
            status = last_pipeline['status']
            return f"GitLab Pipeline Status: {status}"
        else:
            return "No pipelines found."
    else:
        return f"Error fetching GitLab data. Status code: {response.status_code}"


# ServiceNow

def get_incidents(query):
    url = f"{SNOW_INSTANCE}/api/now/table/incident?sysparm_query=short_description={query}&sysparm_limit=5"
    auth = (SNOW_USER, SNOW_PASSWORD)
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        incidents = response.json()['result']
        if incidents:
            details = []
            for incident in incidents:
                short_description = incident.get('short_description', 'N/A')
                status = incident.get('state', 'N/A')
                details.append(f"Incident: {short_description}, Status: {status}")
            return "\n".join(details)
        else:
            return "No incidents found for this query."
    else:
        return f"Error fetching ServiceNow data. Status code: {response.status_code}"


# Prompt builder

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


# 🔁 Call OpenRouter LLM

def ask_openrouter(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistralai/mistral-7b-instruct",  # You can change to llama-3, etc.
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Error communicating with OpenRouter: {e}"


# UI
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
