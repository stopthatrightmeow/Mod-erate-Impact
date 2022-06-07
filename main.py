import logging
import socket
import threading
import yaml
import os
import re
import sqlite3
import requests
import pandas as pd
from dateutil.parser import parse
from urllib.parse import parse_qs, urlencode
from waitress import serve # Waitress for production server VS Flask
from os.path import exists
from flask import Flask, render_template, request
from datetime import datetime, timedelta
from time import sleep

# For main logging purposes
logger = logging.getLogger("impact")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.propagate = False # Apparently fixed my double logging (in console) issue...
fh = logging.FileHandler("./mod-erate_impact.log")
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.setLevel('DEBUG')

# Setup Flask APP
app = Flask(__name__)


def read_yaml():
    # Read in the settings and store for later use
    if exists('./settings.yaml'):
        with open('./settings.yaml', mode='r') as file:
            try:
                config = yaml.safe_load(file)
                logger.info('Successfully Read Configuration File')
                logger.debug(config)
                return config

            except yaml.YAMLError as e:
                logger.error(f'Error in settings.yaml: {e}')
    else:
        logger.error('Unable to find required file: "settings.yaml"')
        exit(1)

# URL For Application Authorization with Twitch.
code = None
@app.route("/authorize", methods=['GET'])
def twitch_auth(client_id, redirect_uri):
    global code
    request_payload = {
        'client_id': client_id,
        'force_verify': 'false',
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'chat:read'
    }
    encoded_payload = urlencode(request_payload)
    url = 'https://id.twitch.tv/oauth2/authorize?' + encoded_payload
    code = parse_qs(request.full_path)
    
    try: 
        # If we have an auth code, pass it along to the get_token function
        if code['/authorize?code'][0]:
            get_token(code=code['/authorize?code'][0])
    except:
        pass
    # Render the page, for the user to click the link to auth the app
    return render_template('auth.html', url=url)

access_token = None
refresh_token = None
def get_token(code, client_id, client_secret, redirect_uri):
    global access_token
    global refresh_token
    
    url = 'https://id.twitch.tv/oauth2/token'
    request_payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }
    
    if code:
        request_payload['grant_type'] = 'authorization_code'
        request_payload['/authorize?code'][0] = code
    elif refresh_token:
        request_payload['grant_type'] = 'refresh_token'
        request_payload['refresh_token'] = refresh_token

    logger.info('')
    r = requests.post(url, data=request_payload).json()
    try:
        access_token = r['access_token']
        refresh_token = r['refresh_token']
    except Exception as e:
        logger.error(f'Unexpected response upon redemption of auth code: {r}, {e}')
        
def validate_token():
    logger.info('Validating token.')
    url = 'https://id.twitch.tv/oauth2/validate'
    r = requests.get(url, headers={'Authorization:' f'Oauth {access_token}'})
    if r.status_code == 200:
        logger.info('Access token is still valid.')
        return True
    elif r.status_code == 401:
        logger.info('Access token invalid.')
        return False
    else:
        logger.error(f'Unrecognized status code on validation: {r.status_code}')
        exit(1)

def read_tokens():    

def write_tokens():
    
def auth_flow():
    if read_tokens(): # Code exists
        if not validate_token():
            get_token()
        else:
            twitch_auth() # User login auth
            get_token()
    write_tokens()
    
    return access_token
    

        
if __name__ == "__main__":
    config = read_yaml()
    redirect_uri = 'https://' + config['srv_domain'] + ':' + config['srv_port'] + '/authorize'
    twitch_auth(client_id=config['client_id'], redirect_uri=redirect_uri)
    
    #serve(app, host='localhost', port=3000, threads=2, url_scheme='https')
    app.run(ssl_context="adhoc", host=config['srv_domain'], port=config['srv_port'])