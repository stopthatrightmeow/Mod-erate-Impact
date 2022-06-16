from decimal import DivisionByZero
import logging
import os
import yaml 
import requests
import socket
import threading
import re
import pandas as pd
from time import sleep
from datetime import datetime, timedelta
from dateutil.parser import parse
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
# General Stat Vars
totals = None
mod_data = None

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
    global twitch_validation_th
    global statistics_th
    global chat_th
    global totals

    # If the code var isn't populated, redirect the user to the twitch auth link
    if code is None:
        return redirect(url_for("twitch_auth_link"))
    # Otherwise head them on over to the main page
    else:
        # If the threads aren't running, start them
        if not chat_th.is_alive():
            chat_th.start()
        if not twitch_validation_th.is_alive():
            twitch_validation_th.start()
        if not statistics_th.is_alive():
            statistics_th.start()

        # Vars
        pongs = str(totals['Total Pongs'] * 2)
        breakdown = {}
        # For front table
        for key, value in totals.items():
            if key not in ['Total Sub Messages', 'Total Messages', 'Total Days Tracked', 'Total Non-Sub Messages', 'Reply Count', 'Total Pongs']:
                breakdown[key] = value

        return render_template('home.html', pong=pongs, channel_name=conf['channel'].title(), 
        total_messages=totals['Total Messages'], total_sub_msgs=totals['Total Sub Messages'],
        total_non_sub_msgs=totals['Total Non-Sub Messages'], total_days_tracked=totals['Total Days Tracked'], num_days_tracked=totals['Total Days Tracked'],
        total_replies=totals['Reply Count'], gen_stats=breakdown)

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

# Mod Status Board
@app.route("/mods", methods=['GET'])
def moderator():
    global conf
    global totals
    global mod_data

        # If the code var isn't populated, redirect the user to the twitch auth link
    if code is None:
        return redirect(url_for("twitch_auth_link"))
    else:
        try:
            # Vars
            pongs = str(totals['Total Pongs'] * 2)

            # Top Talkers    
            df = pd.DataFrame.from_dict(mod_data, orient='index')
            df.sort_values(by=['Total Messages Sent'], inplace=True, ascending=False)
            df.sort_index()
            top_three_talkers = df.head(3).to_html(classes='top_three', index=True, columns=['Total Messages Sent'], index_names=True).replace('border="1"','border="0"').replace('Total Messages Sent', '')

            # Mod_stats
            df = pd.DataFrame.from_dict(mod_data, orient='index')
            df.sort_values(by=['Total Messages Sent', 'Average Messages Per Day', 'Average Time Between Messages (in mins)'], inplace=True, ascending=False)
            df.sort_index()
            table = df.to_html(classes='mod_stats', index=True, columns=['Total Messages Sent',  'Average Messages Per Day',  'Days Active', 'Last Active',  
                    'Average Time Between Messages (in mins)', 'Total Users Replied to Mod', 'Total ! Commands'], 
                    index_names=True).replace('text-align: right', 'text-align: center').replace('border="1"','border="0"')

            return render_template('mods.html', channel_name=conf['channel'].title(), pong=pongs, num_days_tracked=totals['Total Days Tracked'],
                mod_stats=table, top_three_talkers=top_three_talkers)
        except KeyError:
            return render_template('no_data.html', channel_name=conf['channel'].title(), pong=pongs, num_days_tracked=totals['Total Days Tracked'])

@app.route("/about", methods=['GET'])
def about_page():
    global conf
    global code
    global totals
    # If the code var isn't populated, redirect the user to the twitch auth link
    if code is None:
        return redirect(url_for("twitch_auth_link"))
    else:
        pongs = str(totals['Total Pongs'] * 2)
        return render_template('about.html', pong=pongs, channel_name=conf['channel'].title(), num_days_tracked=totals['Total Days Tracked'])


# Grabs the valid login token using the code received in previous steps
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

    except Exception as e:
        logger.error(f'Unexpected response on redeeming authentication code: {e}')
    
# Validate twitch token
def validate_token():  
    # Reference: https://dev.twitch.tv/docs/authentication/validate-tokens
    logger.info('Validating Twitch Token...')
    global access_token
    url = 'https://id.twitch.tv/oauth2/validate'
    try:
        r = requests.get(url, headers={'Authorization': f'OAuth {access_token}'})
        if r.status_code == 200:
            logger.info(f'Access token still valid - Status code: {r.status_code}')
            return True
        elif r.status_code == 401:
            logger.info(f'Access token invalid - Status code: {r.status_code}')
            return False
        else:
            logger.error(f'Unrecognized status code on validation attempt - Status code: {r.status_code}')
    except Exception as e:
        logger.error(f'Unable to validate twitch OAuth tokens: {e}')    

# Takes care of the whole process for re-validation per twitch
def twitch_validation():
    while True:
        results = validate_token()
        if results == False:
            logger.debug('Token has expired; Getting new token.')
            get_tokens()
        elif results == True:
            logger.debug('Token still valid, going back to sleep.')
            sleep(300)
        else:
            logger.debug('Other?... Something is really broken if we ended up here...')
            sleep(3)

# Tracks chat from the IRC
def chat_tracker(server, port, nickname, channel):
    global access_token
    nap_time = 0
    # Fancy regex to cut out all the extra garbage
    # https://pythex.org/ Awesome website!
    # This long mess is used to cleanup the chat stuff for tracking subs/nonsubs/and mods
    pattern = r'((@badge-info=.+?)(?=first-msg))|((flags=.+?)(?=mod))|((room-id=.+?)(?=;);)|((room-id=.+?)(?=;);)|((tmi-sent-ts=.+?)(?=turbo))|((user-id=.+?)(?=user-type=))|((!.+?)(?=#))|((moderator.+?)(?=mod))|((user-type=.+?)((?=:)|(?=mod)))|((reply-parent-display-name=.+?)(?=:))|((@badge-info=.+?)(?=display-name=))|((emotes=.+?)(?=mod=))|((msg-param-sub-plan-.+?)(?= :))|((msg-param-origin-id=.+?)(?=;msg-param-recipient-display-name=))|(msg-param-recipient-id=.+?)(?=PRIVMSG)|((.*CLEARCHAT.*)|(.*USERNOTICE.*)).+?'
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
                    
                    if ':Login authentication failed' in resp.strip():
                        raise Exception('Error Login Authentication failed with Twitch IRC. Have you authenticated with Twitch yet?...')
                    if resp.startswith('PING'):
                        chat_logger.write('PONG\n')
                        sock.send("PONG\n".encode('utf-8'))
                    elif len(resp.strip()) > 0:
                        message = re.sub(pattern, '', resp.strip())
                        if len(message) > 0:
                            chat_logger.write(str(msg_recv_time) + ' - ' + message.replace(';', ' - ').replace('#', ' - ') + '\n')

        except Exception as e:
            logger.warning(f'Unable to connect to Twitch Chat; taking a nap before re-trying in {nap_time} seconds: {e}')
            
            # If it's timed out for 2 hours just exit the program
            if nap_time == 720:
                logger.error(f'Unable to connect to Twitch Chat, reached 2 hours worth of wait time: {e}')
                exit(1)
            else:
                nap_time += 5
                sleep(nap_time)

def statistics():
    while True:
        global totals
        global mod_data
        totals = {
            'Total Messages': 0, 
            'Reply Count': 0, 
            'Total Non-Sub Messages': 0, 
            'Total Sub Messages': 0, 
            'Total Days Tracked': 0,
            'Total Pongs': 0
            }
        mod_data = {}
        mod_list = []
        logger.info('Updating Statistics.')

        try:
            file_path = './chat_logs/'
            chat_files = os.listdir(file_path)
            total_days_tracked = len(chat_files)
        except Exception as e:
            logger.error(f'Unable to open files required for reading statistics: {e}')

        try:
            for each_day in chat_files:
                with open(file_path + each_day, mode='r') as chat_log:
                    # Track total messages per date
                    chat_log_date = each_day.split('_')[0]
                    # Convert the time to something human readable
                    chat_log_date = datetime.strptime(chat_log_date, '%Y-%m-%d')
                    chat_log_date = chat_log_date.strftime("%A, %B %d")

                    if is_date(chat_log_date) == True:
                        totals['Totals for ' + chat_log_date] = {
                            'Total Messages': 0,
                            'Total Sub Messages': 0,
                            'Total Non-Sub Messages': 0,
                            'Reply Count': 0
                        }
                        totals['Total Days Tracked'] += 1
                    
                    for line in chat_log:
                        line = line.strip()

                        # Get PONGS
                        if line == 'PONG':
                            totals['Total Pongs'] += 1

                        # Get total messages
                        if line != 'PONG':
                            totals['Total Messages'] += 1
                            totals['Totals for ' + chat_log_date]['Total Messages'] += 1

                        # If the line starts with a date
                        if is_date(line.split(' - ')[0]) == True:
                            if 'mod=1' in line and 'subscriber=' in line:
                                mod = line.split(' - ')[5].replace(':', '').lower()
                                if mod not in mod_list and mod != ('turbo=0' or 'emote-only=1' or 'emote-only=0'):
                                    mod_list.append(mod)

                        # If twitch bulk sends too much stuff and we can't append a date
                        elif 'first-msg=' == line.split(' - ')[0] and 'subscriber=' in line and 'mod=1' in line and line != ('emote-only=1' or 'emote-only=0'):
                            mod = line.split(' - ')[4].replace(':', '').lower()
                            if mod not in mod_list and mod != 'turbo=0':
                                mod_list.append(mod)

                        # Get replies
                        if len(line) != 0 and line != 'PONG' and 'first-msg=0 - mod=0' in line and '@' in line and (conf['nickname'] and 'tmi.twitch.tv' and 'display-name=' and 'emote-only=' and 'subscriber=' and 'PONG') not in line:
                            totals['Reply Count'] += 1
                            totals['Totals for ' + chat_log_date]['Reply Count'] += 1
                        
                        # General Statistics
                        if 'subscriber=1' in line and (conf['nickname'] or 'tmi.twitch.tv' or 'display-name=' or 'emote-only=') not in line:
                            totals['Total Sub Messages'] += 1
                            totals['Totals for ' + chat_log_date]['Total Sub Messages'] += 1
                        elif 'subscriber=0' in line and (conf['nickname'] or 'tmi.twitch.tv' or 'display-name=' or 'emote-only=') not in line:
                            totals['Total Non-Sub Messages'] += 1
                            totals['Totals for ' + chat_log_date]['Total Non-Sub Messages'] += 1

                # Close the file
                chat_log.close()

        except Exception as e:
            logger.error(f'Unable to get General Stats: {e}')

        # Build out mod information
        for mod in mod_list:
            mod_data[mod] = {
                'Total Messages Sent': 0, 
                'Average Messages Per Day': 0, 
                'Days Active': 0, 
                'Last Active': '', 
                'Average Time Between Messages (in mins)': 0, 
                'total_avg_list': [], 
                'total_avg_per_day': {}, 
                'Total Messages Per Day': {}, 
                'Average Per Day (in mins)': {}, 
                'Total Users Replied to Mod': 0,
                'Total ! Commands': 0,
                'Total Replies Per Day': {},
                'Total ! Commands Per Day': {},
            }

            # Calculate average, and grabs counts for each moderator
            d1 = ''
            d2 = ''
            try:
                for each_day in chat_files:
                    with open(file_path + each_day, mode='r') as chat_log:
                        if is_date(each_day.split('_')[0]) == True:
                            chat_log_date = each_day.split('_')[0]
                            mod_data[mod]['total_avg_per_day'][chat_log_date] = []
                            mod_data[mod]['Total Messages Per Day'][chat_log_date] = 0
                            mod_data[mod]['Total ! Commands Per Day'][chat_log_date] = 0
                            mod_data[mod]['Total Replies Per Day'][chat_log_date] = 0 
                        count = 0
                        for line in chat_log:
                            line = line.strip().lower()
                            # Start counting how many messages the mod sent
                            if mod in line and 'mod=1' in line:
                                mod_data[mod]['Total Messages Sent'] += 1
                                mod_data[mod]['Total Messages Per Day'][chat_log_date] += 1
                                # Grab number of ! commands
                                try:
                                    if line.split(' - ')[6].strip().replace(conf['channel'], '').replace(':', '').split()[0].startswith('!'):
                                        mod_data[mod]['Total ! Commands'] += 1
                                        mod_data[mod]['Total ! Commands Per Day'][chat_log_date] += 1
                                except:
                                    continue
                            # Grab users who replied to Mods 
                            if '@' + mod in line and 'mod=0' in line:
                                mod_data[mod]['Total Users Replied to Mod'] += 1    
                                mod_data[mod]['Total Replies Per Day'][chat_log_date] += 1        
                            # Grab time delta information
                            if mod in line and is_date(line.split(' - ')[0]) == True and count == 0:
                                d1 = line.split(' - ')[0]
                                count += 1
                            elif mod in line and is_date(line.split(' - ')[0]) == True and count == 1:
                                d2 = line.split(' - ')[0]
                                count = 0
                                results = deltaberg(d1, d2)
                                mod_data[mod]['total_avg_list'].append(results)
                                mod_data[mod]['total_avg_per_day'][chat_log_date].append(results)
                    # Close the chat file
                    chat_log.close()
                # Calculate average messages per day
                mod_data[mod]['Average Messages Per Day'] = round(mod_data[mod]['Total Messages Sent'] / total_days_tracked)
            except Exception as e:
                logger.error(f'Struggled calculating average messages per day: {e}')
            
            try:
                if len(mod_data[mod]['total_avg_per_day'].keys()) > 2:
                    for key, value in mod_data[mod]['total_avg_per_day'].items():
                        mod_data[mod]['Average Per Day (in mins)'][key] = 0
                        mod_data[mod]['Days Active'] += 1
                        last_active = list(mod_data[mod]['total_avg_per_day'].keys())[0]
                        last_active = datetime.strptime(last_active, '%Y-%m-%d')
                        last_active = last_active.strftime("%A, %B %d")
                        mod_data[mod]['Last Active'] = last_active
                else:                        
                    mod_data[mod]['Days Active'] = 1
                    mod_data[mod]['Last Active'] = list(mod_data[mod]['total_avg_per_day'].keys())[0]
                    mod_data[mod]['Average Per Day (in mins)'][key] = 0
            except Exception as e:
                logger.error(f'I had problems setting up total averages: {e}')

            # Tries to calculate overall average and updates stuff
            try:
                # Calculate overall Average and update 
                total_reply_time = 0
                for reply_time in mod_data[mod]['total_avg_list']:
                    total_reply_time += reply_time
                mod_data[mod]['Average Time Between Messages (in mins)'] = round(round(total_reply_time / len(mod_data[mod]['total_avg_list'])) / 60, 2)

                # Remove the information as it's no longer needed
                mod_data[mod].pop('total_avg_list')
                mod_data[mod].pop('total_avg_per_day')
            except DivisionByZero:
                continue
            except Exception as e:
                logger.debug(f'Unable to calculate Average Time Between Messages: {e}')
        # Sleep for 3 mins
        sleep(180)

# Cleans up the chat files
def cleanup(num):
    while True:
        try:
            # Cleans up old chat logs for you!
            file_path = './chat_logs/'
            chat_files = os.listdir(file_path)

            current_date = datetime.today()
            new_date = current_date - timedelta(days=num)
            logger.info('Checking for files.')
            for each_day in chat_files:
                if each_day.split('_')[0] <= new_date.strftime("%Y-%m-%d"):
                    logger.info(f'Removed {file_path + each_day} file.')
                    os.remove(file_path + each_day)
            logger.info('Going to sleep for 24 hours.')
            sleep(86400)
        except Exception as e:
            logger.error(f'Unable to cleanup chat logs: {e}')
            sleep(3600)

# Checks if the string is a date or not
def is_date(string, fuzzy=False):
    # Return whether the string can be interpreted as a date.
    try: 
        parse(string, fuzzy=fuzzy)
        return True
    except ValueError:
        return False

# Performs a timedelta calculation of two date strings
def deltaberg(date1, date2, other=False):
    if other == False:
        # Get the time in seconds between two messages
        date_format_str = '%Y-%m-%d %H:%M:%S.%f'
        start = datetime.strptime(date1, date_format_str)
        end =   datetime.strptime(date2, date_format_str)
        time_deltas = end - start
        results = time_deltas.total_seconds() 
        return results
    else:
        # Get the time in seconds between two messages
        date_format_str = '%Y-%m-%d'
        start = datetime.strptime(date1, date_format_str)
        end =   datetime.strptime(date2, date_format_str)
        time_deltas = end - start
        results = time_deltas.total_seconds() 
        return results

if __name__ == '__main__':
    global conf
    global twitch_validation_th
    global chat_th
    global statistics_th
    conf = read_yaml()   

    # Background the Cleanup Function
    clean_th = threading.Thread(target=cleanup, args=(conf['num_days_saved'],))
    clean_th.start()

    # These three are started after authentication with twitch occurs.
    twitch_validation_th = threading.Thread(target=twitch_validation)
    chat_th = threading.Thread(target=chat_tracker, args=(conf['server'], conf['port'], conf['nickname'], conf['channel']))
    statistics_th = threading.Thread(target=statistics)

    # Starts the webserver
    app.run(ssl_context="adhoc", host='127.0.0.1', port=3000)
