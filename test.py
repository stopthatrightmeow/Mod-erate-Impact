import yaml
import socket
import re
import requests
import chardet
from io import BytesIO
from datetime import datetime
import logging
from os.path import exists
from time import sleep, time

# For main logging purposes
logger = logging.getLogger("impact")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.propagate = False # Apparently fixed my double logging (in console) issue...
fh = logging.FileHandler("./testing.log")
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.setLevel('DEBUG')


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
    msg_pattern = r'((@badge-info=.+?)(?=first-msg))|((flags=.+?)(?=mod))|((room-id=.+?)(?=;);)|((room-id=.+?)(?=;);)|((tmi-sent-ts=.+?)(?=turbo))|((user-id=.+?)(?=user-type=))|((!.+?)(?=#))|((moderator.+?)(?=mod))|((user-type=.+?)((?=:)|(?=mod)))|((reply-parent-display-name=.+?)(?=:))|((@badge-info=.+?)(?=display-name=))|((emotes=.+?)(?=mod=))|((msg-param-sub-plan-.+?)(?= :))|((msg-param-origin-id=.+?)(?=;msg-param-recipient-display-name=))|(msg-param-recipient-id=.+?)(?=PRIVMSG)|((.*CLEARCHAT.*)|(.*USERNOTICE.*)).+?'
    joins_pattern = r'!.*JOIN.*'
    parts_pattern = r'!.*PART.*'

    while True:
        try:
            # Connect to the server
            sock = socket.socket()

            sock.connect((server, port))
            
            sock.send(f"PASS {secret}\n".encode('utf-8'))
            sock.send(f"NICK {nickname}\n".encode('utf-8'))
            
            # Used for additional meta-data like join/part
            sock.send("CAP REQ :twitch.tv/commands twitch.tv/tags ".encode('utf-8'))
            
            # Required to grab moderator Information
            sock.send(f"CAP REQ :twitch.tv/commands \n".encode('utf-8'))
            sock.send(f"CAP REQ :twitch.tv/tags \n".encode('utf-8'))
            sock.send(f"CAP REQ :twitch.tv/membership \n".encode('utf-8'))

            # Join Channel
            sock.send(f"JOIN #{channel}\n".encode('utf-8'))
            logger.debug('Connected to Twitch Chat')

            while True:
                log_date = datetime.now()
                log_date = log_date.strftime('%Y-%m-%d')
                with open('./chat_logs/' + log_date + 'TEST2_CHAT.log', mode='a+') as chat_logger:
                    # IRC Connection Stuff
                    resp = sock.recv(2048).decode('utf-8')
                    time_tracker = datetime.now()
                    time_tracker = time_tracker.strftime('%Y-%m-%d %H:%M:%S.%f')

                    if resp.startswith('PING'):
                        chat_logger.write('PONG\n')
                        sock.send("PONG\n".encode('utf-8'))    
                    elif len(resp.strip()) > 0:
                        if 'JOIN' in resp.strip():
                            message = re.sub(joins_pattern, '', resp.strip())
                            chat_logger.write(str(time_tracker) + ' - ' + message.replace(':', '') + ' - Has Joined')
                        elif 'PART' in resp.strip():
                            message = re.sub(parts_pattern, '', resp.strip())
                            chat_logger.write(str(time_tracker) + ' - ' + message.replace(':', '') + ' - Has Parted')
                        else:
                            message = re.sub(msg_pattern, '', resp.strip())
                            chat_logger.write(str(time_tracker) + ' - ' + message.replace(';', ' - ').replace('#', ' - ') + '\n')

        except Exception as e:
            logger.warning(f'Unable to connect to Twitch Chat; taking a nap before re-trying in {nap_time} seconds: {e}')
            # If it's timed out for 2 hours just exit the program
            if nap_time == 720:
                logger.error(f'Unable to connect to Twitch Chat, reached 2 hours worth of wait time: {e}')
                exit(1)
            else:
                nap_time += 5
                sleep(nap_time)


def get_auth_token():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 3000))
        s.listen()
        conn, addr = s.accept()
        with conn:
            print('Connected by', addr)
            while True:
                data = conn.recv(4096)
                print(fromhex(data))
                if not data:
                    break
                #conn.sendall(data)


    #r = requests.get('https://id.twitch.tv/oauth2/authorize?response_type=code&client_id=tev5matdoe8saq7ukb0dk6n5wh1n1t&redirect_uri=https://127.0.0.1:3000&scope=chat:read')
    



if __name__ == '__main__': 
    config = read_yaml()
    #chat_tracker(server=config['server'], port=config['port'], nickname=config['nickname'], secret=config['oauth_secret'], channel=config['channel'])
    get_auth_token()