# slack.py

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import json
import os
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
from integrations.integration_item import IntegrationItem

# HubSpot OAuth endpoints
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
CLIENT_ID = "991fcac1-af71-4ffc-8663-c60e4fa4645a"
CLIENT_SECRET = "fc9dc13c-3bc0-4cb7-9410-c7202fc1b7fb"
REDIRECT_URI = "http://localhost:8000/integrations/hubspot/oauth2callback"

async def authorize_hubspot(user_id, org_id):
    """
    Initiates the OAuth2 authorization flow for HubSpot
    """
    # Create some data here
    state = json.dumps({
        'user_id': user_id,
        'org_id': org_id
    })
    
    # Updated scopes 
    scopes = (
        "crm.objects.contacts.read "
        "crm.objects.contacts.write "
        "crm.objects.companies.read "
        "crm.objects.deals.read"
    )
    
    authorization_url = (
        f"{HUBSPOT_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&state={state}"
    )
    
    return authorization_url
#this is concerned with the callback from hubspot
async def oauth2callback_hubspot(request: Request):
    """
    Handles the OAuth2 callback from HubSpot
    """
    # Get authorization code from request parameters
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    # Get user_id and org_id from state parameter
    state = request.query_params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="State parameter not found")

    try:
        state_data = json.loads(state)
        user_id = state_data.get('user_id')
        org_id = state_data.get('org_id')
    except:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Request access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code
            }
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to get access token: {token_response.text}")

    # Parse token response
    token_data = token_response.json()
    
    # WE HAVE USED REDIS TO STORE THE CREDENTIALS USING KEYS
    await add_key_value_redis(
        f'hubspot_credentials:{org_id}:{user_id}', 
        json.dumps(token_data),
        expire=600
    )
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieves the stored HubSpot credentials
    """
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found")
    
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

#this is concerned with the items that are returned from hubspot (Basically Data Retrival)
async def get_items_hubspot(credentials):
    """
    Retrieves contacts, companies, and deals from HubSpot
    Returns a list of IntegrationItem objects
    """
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    items = []
    
    async with httpx.AsyncClient() as client:
        # Get Contacts
        contacts_response = await client.get(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": 100}
        )
        
        if contacts_response.status_code == 200:
            contacts = contacts_response.json().get('results', [])
            for contact in contacts:
                properties = contact.get('properties', {})
                items.append(
                    IntegrationItem(
                        id=f"contact_{contact.get('id')}",
                        name=f"{properties.get('firstname', '')} {properties.get('lastname', '')}".strip() or "Unnamed Contact",
                        type='contact',
                        creation_time=contact.get('createdAt'),
                        last_modified_time=contact.get('updatedAt'),
                        url=f"https://app.hubspot.com/contacts/{properties.get('hs_object_id')}",
                        visibility=True
                    )
                )

        # Get Companies
        companies_response = await client.get(
            "https://api.hubapi.com/crm/v3/objects/companies",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": 100}
        )
        
        if companies_response.status_code == 200:
            companies = companies_response.json().get('results', [])
            for company in companies:
                properties = company.get('properties', {})
                items.append(
                    IntegrationItem(
                        id=f"company_{company.get('id')}",
                        name=properties.get('name', 'Unnamed Company'),
                        type='company',
                        creation_time=company.get('createdAt'),
                        last_modified_time=company.get('updatedAt'),
                        url=f"https://app.hubspot.com/companies/{properties.get('hs_object_id')}",
                        visibility=True
                    )
                )

        # Get Deals
        deals_response = await client.get(
            "https://api.hubapi.com/crm/v3/objects/deals",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": 100}
        )
        
        if deals_response.status_code == 200:
            deals = deals_response.json().get('results', [])
            for deal in deals:
                properties = deal.get('properties', {})
                items.append(
                    IntegrationItem(
                        id=f"deal_{deal.get('id')}",
                        name=properties.get('dealname', 'Unnamed Deal'),
                        type='deal',
                        creation_time=deal.get('createdAt'),
                        last_modified_time=deal.get('updatedAt'),
                        url=f"https://app.hubspot.com/deals/{properties.get('hs_object_id')}",
                        visibility=True
                    )
                )

        print("HubSpot Integration Items:")
        for item in items:
            print(f"Type: {item.type}, Name: {item.name}, ID: {item.id}")
            print(f"Created: {item.creation_time}, Updated: {item.last_modified_time}")
            print(f"URL: {item.url}")
            print("---")

        return items

async def create_integration_item_metadata_object(response_json):
    # TODO
    pass