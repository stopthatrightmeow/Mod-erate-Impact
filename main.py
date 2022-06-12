import logging
from os import access
import yaml
import requests
import socket
import threading
import re
from time import sleep
from datetime import datetime
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
    global conf
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
        'scope': 'chat:edit chat:read'
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

def twitch_validation():
    while True:
        if validate_token() == False:
            logger.debug('Getting new token.')
            get_tokens()
            return True
        elif validate_token() == True:
            logger.debug('Token still valid.')
            sleep(300)
            return True
        else:
            logger.debug('Other?...')
            sleep(3)
            return False


def chat_tracker(server, port, nickname, channel):
    global access_token
    nap_time = 0
    # Fancy regex to cut out all the extra garbage
    # https://pythex.org/ Awesome website!
    # This long mess is used to cleanup the chat stuff for tracking subs/nonsubs/and mods
    pattern = r'((@badge-info=.+?)(?=first-msg))|((flags=.+?)(?=mod))|((room-id=.+?)(?=;);)|((room-id=.+?)(?=;);)|((tmi-sent-ts=.+?)(?=turbo))|((user-id=.+?)(?=user-type=))|((!.+?)(?=#))|((moderator.+?)(?=mod))|((user-type=.+?)((?=:)|(?=mod)))|((reply-parent-display-name=.+?)(?=:))|((@badge-info=.+?)(?=display-name=))|((emotes=.+?)(?=mod=))|((msg-param-sub-plan-.+?)(?= :))|((msg-param-origin-id=.+?)(?=;msg-param-recipient-display-name=))|(msg-param-recipient-id=.+?)(?=PRIVMSG)|((.*CLEARCHAT.*)|(.*USERNOTICE.*)).+?'
    auth_failure = r'\W(:Login authentication failed)'

    while True:
        try:
            # Connect to the server
            sock = socket.socket()
            sock.connect((server, port))

            # Send Authentication/Nickname
            sock.send(f"PASS oauth:{access_token}\n".encode('utf-8'))
            sock.send(f"NICK {nickname}\n".encode('utf-8'))

            # Required to grab moderator information
            # Reference: https://dev.twitch.tv/docs/irc/capabilities
            sock.send(f"CAP REQ :twitch.tv/commands \n".encode('utf-8'))
            sock.send(f"CAP REQ :twitch.tv/tags \n".encode('utf-8'))
            sock.send(f"CAP REQ :twitch.tv/membership \n".encode('utf-8'))
            # Join Channel
            sock.send(f"JOIN #{channel}\n".encode('utf-8'))
            logger.debug('Connected to Twitch Chat')

            while True:
                # Time formatting
                log_date = datetime.now()
                log_date = log_date.strftime('%Y-%m-%d')
                with open('./chat_logs/' + log_date + '_twitch_chat.log', mode='a+') as chat_logger:
                    # Reading in what the IRC sent us
                    resp = sock.recv(2048).decode('utf-8')
                    msg_recv_time = datetime.now()
                    msg_recv_time = msg_recv_time.strftime('%Y-%m-%d %H:%M:%S.%f')
                    chat_logger.write(resp.strip() + '\n')
                    if ':Login authentication failed' in resp.strip():
                        raise Exception('Error Login Authentication failed with Twitch IRC. Have you authenticated with Twitch yet?...')
                    if resp.startswith('PING'):
                        chat_logger.write('PONG\n')
                        sock.send("PONG\n".encode('utf-8'))

        except Exception as e:
            logger.warning(f'Unable to connect to Twitch Chat; taking a nap before re-trying in {nap_time} seconds: {e}')
            
            # If it's timed out for 2 hours just exit the program
            if nap_time == 720:
                logger.error(f'Unable to connect to Twitch Chat, reached 2 hours worth of wait time: {e}')
                exit(1)
            else:
                nap_time += 5
                sleep(nap_time)
                        


    
if __name__ == '__main__':
    global conf
    conf = read_yaml()

    # Start and re-auth 
    twitch_validation_th = threading.Thread(target=twitch_validation)
    twitch_validation_th.start()
    valid = twitch_validation_th.join()
    logger.debug(f'Twitch Validation: {valid}')
    chat_th = threading.Thread(target=chat_tracker, args=(conf['server'], conf['port'], conf['nickname'], conf['channel']))

    #while twitch_validation() and chat_th.is_alive() is False and code is not None:
    #    chat_th.start()

    
    app.run(ssl_context="adhoc", host='127.0.0.1', port=3000)
