import logging
import socket
import threading
import yaml
import os
import re
import pandas as pd
from dateutil.parser import parse
from waitress import serve # Waitress for production server VS Flask
from os.path import exists
from flask import Flask, render_template
from datetime import datetime, timedelta
from time import sleep

# For main logging purposes
logger = logging.getLogger("impact")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
fh = logging.FileHandler("./mod-erate_impact.log")
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.setLevel('INFO')

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

def chat_tracker(server, port, nickname, secret, channel):
    # For timeout purposes.
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
            
            sock.send(f"PASS {secret}\n".encode('utf-8'))
            sock.send(f"NICK {nickname}\n".encode('utf-8'))
            
            # Reguired to grab moderator Information
            sock.send(f"CAP REQ :twitch.tv/commands \n".encode('utf-8'))
            sock.send(f"CAP REQ :twitch.tv/tags \n".encode('utf-8'))
            # Join Channel
            sock.send(f"JOIN #{channel}\n".encode('utf-8'))

            
            logger.debug('Starting Chat Tracker')
            while True:
                log_date = datetime.now()
                log_date = log_date.strftime('%Y-%m-%d')
                with open('./chat_logs/' + log_date + '_twitch_chat.log', mode='a+') as chat_logger:
                    # IRC Connection Stuff
                    resp = sock.recv(2048).decode('utf-8')
                    time_tracker = datetime.now()
                    time_tracker = time_tracker.strftime('%Y-%m-%d %H:%M:%S.%f')

                    if resp.startswith('PING'):
                        chat_logger.write('PONG\n')
                        sock.send("PONG\n".encode('utf-8'))    
                    elif len(resp.strip()) > 0:
                        message = re.sub(pattern, '', resp.strip())
                        if len(message) > 0:
                            chat_logger.write(str(time_tracker) + ' - ' + message.replace(';', ' - ').replace('#', ' - ') + '\n')

        except Exception as e:
            logger.error(f'Unable to connect to Twitch Chat: {e}')
            sleep(nap_time)
            nap_time += 5

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

def get_pongs():
    # Find all the PONGS
    try:
        # Directory Stuff
        total_pongs = 0
        file_path = './chat_logs/'
        chat_files = os.listdir(file_path) 
        for each_day in chat_files:
            with open(file_path + each_day, mode='r') as chat_log:
                for line in chat_log:
                    if 'PONG' in line:
                        total_pongs += 1
                
        results = str(total_pongs * 2)
        return results

    except Exception as e:
        logger.error(f'Unable to open chat log: {e}')
        results = 'NULL'
        return results

def statistics():
    try:
        file_path = './chat_logs/'
        chat_files = os.listdir(file_path) 
        total_days_tracked = len(chat_files)
    except Exception as e:
        logger.error('Unable to open files required for')

    totals = {'Total Messages': 0, 'Reply Count': 0, 'Total Non-Sub Messages': 0, 'Total Sub Messages': 0, 'Total Days Tracked': 0}
    mod_data = {}
    mod_list = []


    try:
        """
        This chunk does a few things:
        1. Pulls out moderators
        2. Pulls out total messages (across all files)
        3. Pulls out total messages per day
        4. Pulls out the number of replies
        5. Number of days tracked
        """
        for each_day in chat_files:
            with open(file_path + each_day, mode='r') as chat_log:
                # Setting things up to track total messages by date
                if is_date(each_day.split('_')[0]) == True:
                    chat_log_date = each_day.split('_')[0]
                    totals['Total for ' + chat_log_date] = 0
                    #totals[chat_log_date + '-Replies'] = 0
                    totals['Total Days Tracked'] += 1
                
                for line in chat_log:
                    # Get total Messages
                    if line.strip() != 'PONG' and conf['nickname'] not in line.strip() and 'tmi.twitch.tv' not in line.strip() and 'display-name=' not in line.strip() and 'emote-only=' not in line.strip():
                        totals['Total Messages'] += 1
                        totals['Total for ' + chat_log_date] += 1
                        
                    # If the line starts with a date
                    if is_date(line.split(' - ')[0]) == True:
                        if 'mod=1' in line and 'subscriber=' in line:
                            mod = line.split(' - ')[5].replace(':', '')
                            if mod not in mod_list and mod.lower() != 'turbo=0' and mod.lower() != 'emote-only=1' and mod.lower() != 'emote-only=0':
                                mod_list.append(mod)

                    # If twitch bulk sends too much stuff and we can't append a date
                    elif 'first-msg=' == line.split(' - ')[0] and 'subscriber=' in line and 'mod=1' in line and mod.lower() != 'emote-only=1' and mod.lower() != 'emote-only=0':
                        mod = line.split(' - ')[4].replace(':', '')
                        if mod not in mod_list and mod.lower() != 'turbo=0':
                            mod_list.append(mod)
                            
                    # Otherwise while we are here let's get a count for how many replies
                    if 'subscriber=' not in line and 'PONG' not in line and len(line) != 0 and conf['nickname'] not in line.strip() and 'tmi.twitch.tv' not in line.strip() and 'display-name=' not in line.strip() and 'emote-only=' not in line.strip():
                        totals['Reply Count'] += 1
                        #totals[chat_log_date + '-Replies'] += 1
                    
                    # General Stats
                    if 'subscriber=1' in line and conf['nickname'] not in line.strip() and 'tmi.twitch.tv' not in line.strip() and 'display-name=' not in line.strip() and 'emote-only=' not in line.strip():
                        totals['Total Sub Messages'] += 1
                    elif 'subscriber=0' in line and conf['nickname'] not in line.strip() and 'tmi.twitch.tv' not in line.strip() and 'display-name=' not in line.strip() and 'emote-only=' not in line.strip():
                        totals['Total Non-Sub Messages'] += 1

            chat_log.close()
    except Exception as e:
        logger.error(f'Unable to find the mods: {e}')

    # Setting up data fields

    for mod in mod_list:
        mod_data[mod] = {'Total Messages Sent': 0, 'Average Messages Per Day': 0, 'Days Active': 0, 'Last Active': '', 
            'Average Time Between Messages (in mins)': 0, 'total_avg_list': [], 'total_avg_per_day': {}, 'Total Messages Per Day': {}, 'Average Per Day (in mins)': {}}


        # Calculate average between messages sent
        d1 = ''
        d2 = ''
        try:
            for each_day in chat_files:
                with open(file_path + each_day, mode='r') as chat_log:
                    if is_date(each_day.split('_')[0]) == True:
                        chat_log_date = each_day.split('_')[0]
                        mod_data[mod]['total_avg_per_day'][chat_log_date] = []
                        mod_data[mod]['Total Messages Per Day'][chat_log_date] = 0
                    count = 0
                    for line in chat_log:
                        # Start counting how many messages the mod sent
                        if mod in line:
                            mod_data[mod]['Total Messages Sent'] += 1
                            mod_data[mod]['Total Messages Per Day'][chat_log_date] += 1

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
                chat_log.close()

            # Calculate average messages per day
            mod_data[mod]['Average Messages Per Day'] = round(mod_data[mod]['Total Messages Sent'] / total_days_tracked)

            # Shit show, need to fix.
            try:
                time_to_beat = 0
                for key, value in mod_data[mod]['total_avg_per_day'].items():
                    mod_data[mod]['Average Per Day (in mins)'][key] = 0
                    # Calculate days active
                    if len(value) != 0:
                        mod_data[mod]['Days Active'] += 1
                        # Calculate "Last Active" date
                        if key == datetime.today().strftime('%Y-%m-%d'):
                            mod_data[mod]['Last Active'] = key
                        elif time_to_beat == 0:
                            time_to_beat = round(deltaberg(key, datetime.today().strftime('%Y-%m-%d'), other=True))
                            mod_data[mod]['Last Active'] = key
                        elif round(deltaberg(key, datetime.today().strftime('%Y-%m-%d'), other=True)) <= time_to_beat:
                            mod_data[mod]['Last Active'] = key
                            time_to_beat = round(deltaberg(key, datetime.today().strftime('%Y-%m-%d'), other=True))
                                        
                        # Calculate average time between messages (in mins) per day
                        avg_for_day = 0
                        for each_reply in value:
                            avg_for_day += each_reply
                        mod_data[mod]['Average Per Day (in mins)'][key] = round(round(avg_for_day) / len(value) / 60, 2)

                        # Remove the information as it's no longer needed
            except Exception as e:
                logger.error(f'Unable to calculate Average Per Day: {e}')

            try:
                # Calculate overall Average and update 
                total_reply_time = 0
                for reply_time in mod_data[mod]['total_avg_list']:
                    total_reply_time += reply_time
                mod_data[mod]['Average Time Between Messages (in mins)'] = round(round(total_reply_time / len(mod_data[mod]['total_avg_list'])) / 60, 2)

                # Remove the information as it's no longer needed
                mod_data[mod].pop('total_avg_list')
                mod_data[mod].pop('total_avg_per_day')


            except Exception as e:
                logger.error(f'Unable to calculate Average Time Between Messages: {e}')

        except Exception as e:
            logger.error(f'Unable to calculate averages: {e}')

    return (totals, mod_data)


def is_date(string, fuzzy=False):
    # Return whether the string can be interpreted as a date.
    try: 
        parse(string, fuzzy=fuzzy)
        return True

    except ValueError:
        return False

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

### WEB STUFF ###
@app.route("/about", methods=['GET'])
def about_page():
    conf = read_yaml()
    pong = get_pongs()
    data = statistics()

    totals = data[0]
    return render_template('about.html', pong=pong, channel_name=conf['channel'].title(), num_days_tracked=totals['Total Days Tracked'])

# Home Page
@app.route("/", methods=['GET'])
def home_page():
    conf = read_yaml()
    pong = get_pongs()
    data = statistics()
    totals = data[0]
    
    breakdown = {}
    for key, value in totals.items():
        if key not in ['Total Sub Messages', 'Total Messages', 'Total Days Tracked', 'Total Non-Sub Messages', 'Reply Count']:
            breakdown[key] = value


    return render_template('home.html', pong=pong, channel_name=conf['channel'].title(), 
        total_messages=totals['Total Messages'], total_sub_msgs=totals['Total Sub Messages'],
        total_non_sub_msgs=totals['Total Non-Sub Messages'], total_days_tracked=totals['Total Days Tracked'], num_days_tracked=totals['Total Days Tracked'],
        total_replies=totals['Reply Count'], gen_stats=breakdown)

# Mod Status Board
@app.route("/mods", methods=['GET'])
def moderator():
    conf = read_yaml()
    pong = get_pongs()
    data = statistics()
    totals = data[0]
    mod_stats = data[1]
    try:
        # Top Talkers    
        df = pd.DataFrame.from_dict(mod_stats, orient='index')
        df.sort_values(by=['Total Messages Sent'], inplace=True, ascending=False)
        df.sort_index()
        top_three_talkers = df.head(3).to_html(classes='top_three', index=True, columns=['Total Messages Sent'], index_names=True).replace('border="1"','border="0"').replace('Total Messages Sent', '')

        # Mod_stats
        df = pd.DataFrame.from_dict(mod_stats, orient='index')
        df.sort_values(by=['Total Messages Sent'], inplace=True, ascending=False)
        df.sort_index()
        table = df.to_html(classes='mod_stats', index=True, columns=['Total Messages Sent',  'Average Messages Per Day',  'Days Active', 'Last Active',  'Average Time Between Messages (in mins)'], index_names=True).replace('text-align: right', 'text-align: center').replace('border="1"','border="0"')
        mod_stats=table

        return render_template('mods.html', channel_name=conf['channel'].title(), pong=pong, num_days_tracked=totals['Total Days Tracked'],
            mod_stats=table, top_three_talkers=top_three_talkers)
    except KeyError:
        return render_template('no_data.html', channel_name=conf['channel'].title(), pong=pong, num_days_tracked=totals['Total Days Tracked'])

if __name__ == "__main__":
    try:
        # Read Settings
        global conf
        conf = read_yaml()

        # Backgrounding the Cleanup Function
        clean_th = threading.Thread(target=cleanup, args=(conf['num_days_saved'],))
        clean_th.start()
        
        # Backgrounding the Chat Tracker Function in it's own thread
        chat_th = threading.Thread(target=chat_tracker, args=(conf['server'], conf['port'], conf['nickname'], conf['oauth_secret'], conf['channel']))
        chat_th.start()

        serve(app, host='0.0.0.0', port=8080, threads=6)

    except KeyboardInterrupt:
        exit()