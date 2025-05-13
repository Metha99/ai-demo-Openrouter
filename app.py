import os
import requests
import streamlit as st
from datetime import datetime, timedelta
import json

# Get secrets from Streamlit
AZURE_TENANT_ID = st.secrets["AZURE_TENANT_ID"]
AZURE_CLIENT_ID = st.secrets["AZURE_CLIENT_ID"]
AZURE_CLIENT_SECRET = st.secrets["AZURE_CLIENT_SECRET"]
AZURE_SUBSCRIPTION_ID = st.secrets["AZURE_SUBSCRIPTION_ID"]
AZURE_RESOURCE_GROUP = st.secrets["AZURE_RESOURCE_GROUP"]
AZURE_VM_NAME = st.secrets["AZURE_VM_NAME"]

# OpenRouter or LLM proxy (assuming it's used here)
LLM_API_URL = st.secrets["LLM_API_URL"]
LLM_API_KEY = st.secrets["LLM_API_KEY"]


def get_azure_token():
    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    body = {
        "grant_type": "client_credentials",
        "client_id": AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope": "https://management.azure.com/.default"
    }
    response = requests.post(url, headers=headers, data=body)
    response.raise_for_status()
    return response.json().get("access_token")


def get_vm_status(token):
    url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{AZURE_VM_NAME}/instanceView?api-version=2022-08-01"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return {"error": response.text}


def get_vm_metrics(token):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{AZURE_RESOURCE_GROUP}/providers/Microsoft.Compute/virtualMachines/{AZURE_VM_NAME}/providers/microsoft.insights/metrics"
    params = {
        "api-version": "2018-01-01",
        "metricnames": "Percentage CPU,Disk Read Bytes,Disk Write Bytes",
        "timespan": f"{start_time.isoformat()}Z/{end_time.isoformat()}Z",
        "interval": "PT5M",
        "aggregation": "Average"
    }
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    return {"error": response.text}


def ask_llm(prompt):
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-0106",  # Adjust as needed
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(LLM_API_URL, headers=headers, json=payload)
    try:
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "LLM returned no message.")
    except Exception as e:
        return f"LLM call failed: {str(e)}"


st.title("Unified AI Assistant")
st.write("Enter your customer issue/query:")
user_input = st.text_area("", height=100)

if st.button("Submit"):
    if not user_input:
        st.warning("Please enter a query.")
    else:
        token = get_azure_token()
        vm_status = get_vm_status(token)
        vm_metrics = get_vm_metrics(token)

        summary = ""

        if "error" in vm_status:
            summary += f"Azure VM status fetch error: {vm_status['error']}\n"
        else:
            summary += f"Azure VM is running.\n"

        if "error" in vm_metrics:
            summary += f"Azure metrics fetch error: {vm_metrics['error']}\n"
        else:
            cpu_data = vm_metrics.get("value", [])[0] if vm_metrics.get("value") else {}
            summary += f"Azure VM CPU Metrics: {json.dumps(cpu_data, indent=2)}\n"

        final_prompt = f"Query: {user_input}\n\nAzure Info:\n{summary}\n\nGive a clear summary and actionable insights."
        llm_response = ask_llm(final_prompt)

        st.subheader("Unified AI Response:")
        st.write(llm_response)
