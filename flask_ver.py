from flask import Flask, render_template, request
from flask_oauthlib.client import OAuth
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from waitress import serve
import requests

app = Flask(__name__) 


# Route for application authorization
# Take a look @ this https://www.kianryan.co.uk/2022-05-24-twitch-authentication-with-python/ for reference to what this is doing
code = None
@app.route("/authorize", methods=['GET'])
def twitch_auth():
    global code

    # Create the URL for the authorization request
    request_payload = {
        "client_id": "tev5matdoe8saq7ukb0dk6n5wh1n1t",
        "force_verify": 'false',
        "redirect_uri": 'https://127.0.0.1:3000/authorize',
        "response_type": "code",
        "scope": 'chat:read'
    }
    encoded_payload = urlencode(request_payload)
    url = 'https://id.twitch.tv/oauth2/authorize?' + encoded_payload
    code = parse_qs(request.full_path)
    
    try:
        if code['/authorize?code'][0]:
            get_tokens(code=code['/authorize?code'][0])
    except:
        pass
    
    return render_template('auth.html', url=url)


access_token = None
refresh_token = None
def get_tokens(code):
    global access_token
    global refresh_token

    url = 'https://id.twitch.tv/oauth2/token'
    request_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }

    if code: 
        request_payload['grant_type'] = 'authorization_code'
        request_payload['/authorize?code'][0] = code
    elif refresh_token:
        request_payload['grant_type'] = 'refresh_token'
        request_payload['refresh_token'] = refresh_token
    else:
        raise Exception('No code or refresh token to exchange.')
    
    r = requests.post(url, data=request_payload).json()

    try:
        access_token = r['access_token']
        refresh_token = r['refresh_token']
    except Exception as e:
        print('Unexpected response on redeeming auth code: {r}, {e}')


def validate():
    url = 'https://id.twitch.tv/oauth2/validate'
    r = requests.get(url, headers={'Authorization:': f'Oauth {access_token}'})
    if r.status_code == 200:
        print('Access token still valid.')
    elif r.status_code == 401:
        print('Access token invalid.')
    else:
        raise Exception(f'Unrecognized status code on validate: {r.status_code}')

if __name__ == '__main__':
    #serve(app, host='localhost', port=3000, threads=2, url_scheme='https')
    app.run(ssl_context="adhoc", host='localhost', port=3000)