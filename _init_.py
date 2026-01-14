import json
import os
import requests
from openai import AzureOpenAI

def main(req):
    incident_sys_id = req.params.get("sys_id")
    if not incident_sys_id:
        return "sys_id missing"

    token_url = f"{os.environ['SNOW_INSTANCE_URL']}/oauth_token.do"

    token_resp = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "client_id": os.environ["SNOW_CLIENT_ID"],
            "client_secret": os.environ["SNOW_CLIENT_SECRET"],
            "username": os.environ["SNOW_USERNAME"],
            "password": os.environ["SNOW_PASSWORD"]
        }
    ).json()

    access_token = token_resp.get("access_token")
    if not access_token:
        return token_resp

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    incident = requests.get(
        f"{os.environ['SNOW_INSTANCE_URL']}/api/now/table/incident/{incident_sys_id}",
        headers=headers
    ).json()["result"]

    with open("incident_kb.json") as f:
        kb = json.load(f)

    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version="2024-02-15-preview"
    )

    prompt = f'''
Using only the knowledge base below, correct the incident.

Knowledge Base:
{json.dumps(kb)}

Incident:
{json.dumps(incident)}

Return JSON with:
major_incident, recommended_priority, recommended_category,
recommended_assignment_group, confidence, reasoning
'''

    ai_resp = client.chat.completions.create(
        model="incident-poc",
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(ai_resp.choices[0].message.content)

    requests.patch(
        f"{os.environ['SNOW_INSTANCE_URL']}/api/now/table/incident/{incident_sys_id}",
        headers=headers,
        json={
            "priority": result["recommended_priority"],
            "category": result["recommended_category"],
            "assignment_group": result["recommended_assignment_group"],
            "work_notes": result["reasoning"]
        }
    )

    return result
