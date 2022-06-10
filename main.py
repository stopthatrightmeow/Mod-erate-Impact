import logging
import yaml
import requests
from urllib.parse import parse_qs, urlencode
from os.path import exists
from flask import Flask, render_template, redirect, url_for, request

# For logging purposes
logger = logging.getLogger("impact")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
fh = logging.FileHandler("./mod-erate_impact.log")
fh.setFormatter(formatter)
logger.addHandler(fh)
# Change later to INFO instead of DEBUG cause no one needs all your garbage notes!
logger.setLevel('DEBUG')

app = Flask(__name__)

# Twitch Auth Information
code = None
access_token = None
refresh_token = None

# Reads in the configuration file settings
def read_yaml():   
    if exists('./settings.yaml'):
        with open('./settings.yaml', mode='r') as file:
            try:
                config = yaml.safe_load(file)
                logger.info('Successfully read configuration file.')
                logger.debug(config)
                return config
                
            except yaml.YAMLError as e:
                logger.error(f'Error in settings.yaml file: {e}')
    else:
        logger.error('Unable to find required file: "settings.yaml"')
        exit(1)


# Home Page, Redirect if no code exists (get twitch authentication)
@app.route("/", methods=['GET'])
def index():
    global code

    # If the code var isn't populated, redirect the user to the twitch auth link
    if code is None:
        return redirect(url_for("twitch_auth_link"))
    # Otherwise head them on over to the main page
    else:
        get_tokens()
        return('Something Here Temporarily')

# Renders twitch oauth authorization link, user interaction required
@app.route('/authorize', methods=['GET'])
def twitch_auth_link():
    
    # Other Stuff, break out later
    redirect_uri = 'https://127.0.0.1:3000/authorize'
    client_id = 'tev5matdoe8saq7ukb0dk6n5wh1n1t'
    
    global code
    # Create the URL for the auth request
    request_payload = {
        'client_id': client_id,
        'force_verify': 'false',
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'chat:read'
    }
    
    encoded_payload = urlencode(request_payload)
    url = 'https://id.twitch.tv/oauth2/authorize?' + encoded_payload
    try:
        code = parse_qs(request.full_path)['/authorize?code'][0]
        logger.debug(code)
        return redirect(url_for('index'))
    except Exception as e:
        logger.warning(f'Twitch authentication has not happened yet: {e}')
        return render_template('auth.html', url=url)

def get_tokens():
    # Setup global vars
    global code
    global access_token
    global refresh_token
    
    # Other Stuff, break out later
    redirect_uri = 'https://127.0.0.1:3000/authorize'
    client_id = 'tev5matdoe8saq7ukb0dk6n5wh1n1t'
    client_secret = ''
    
    # Setup beginning payload stuff
    url = 'https://id.twitch.tv/oauth2/token'
    request_payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri    
    }
    
    # Uses the Twitch authorization code to get an access_token and refresh_token
    if code is not None and (access_token or refresh_token) is None:
        request_payload['grant_type'] = 'authorization_code'
        request_payload['code'] = code
        logger.debug(request_payload)
    # Uses the refresh_token to get a new access_token and new refresh_token
    elif code is not None and (access_token and refresh_token) is not None:
        request_payload['grant_type'] = 'refresh_token'
        request_payload['refresh_token'] = refresh_token
    
    try:
        r = requests.post(url, data=request_payload).json()
        access_token = r['access_token']
        refresh_token = r['refresh_token']
        logger.debug(f'Access token: {access_token}')
        logger.debug(f'Refresh token: {refresh_token}')
        validate_token()
    except Exception as e:
        logger.error(f'Unexpected response on redeeming authentication code: {e}')
    
# Validate twitch token
def validate_token():  
    # Reference: https://dev.twitch.tv/docs/authentication/validate-tokens
    logger.debug('Validating Twitch Token')
    global access_token
    url = 'https://id.twitch.tv/oauth2/validate'
    try:
        r = requests.get(url, headers={'Authorization': f'OAuth {access_token}'})
        if r.status_code == 200:
            logger.debug(f'Access token still valid - Status code: {r.status_code}')
            return True
        elif r.status_code == 401:
            logger.debug(f'Access token invalid - Status code: {r.status_code}')
            return False
        else:
            logger.error(f'Unrecognized status code on validation attempt - Status code: {r.status_code}')
    except Exception as e:
        logger.error(f'Unable to validate twitch OAuth tokens: {e}')    

def oauth_flow(check=True):
    if validate_token() == False and check == True:
        get_tokens()
    else:
        validate_token()
        
    
    
if __name__ == '__main__':
    global conf
    conf = read_yaml()  
    app.run(ssl_context="adhoc", host='127.0.0.1', port=3000)
