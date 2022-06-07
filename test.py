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
        
# Connect to SQL Database
def sql_connection():
    logger.info('Preparing to init the database.')
    # Connect to the database file
    try:
        conn = sqlite3.connect('./database.db')
        logger.info('Successfully connected to database file.')
    except Exception as e:
        logger.error(f'Unable to connect to local database file: {e}')
        exit(1)
        
    return conn

# init the SQL database
def init_database(conn=sql_connection()):
    # Create the required tables if they don't already exist
    try:
        cursor = conn.cursor()
        
        # Create Users table
        cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, moderator INT, subscriber INT, turbo INT, messages_sent INT)")
        logger.debug('Created table "users".')
        
        # Create Messages table
        cursor.execute("CREATE TABLE IF NOT EXISTS messages (username TEXT, date TEXT, message TEXT, first_message INT)")
        logger.debug('Created table "messages".')
        
        conn.close()
        logger.info('Successfully created required tables!')
        
    except Exception as e:
        logger.error(f'Unable to init database: {e}')
        exit(1)
   
    # Reset YAML file
    with open('./settings.yaml', mode='r') as file:
        config = yaml.safe_load(file)
        config['first_run'] = False
        file.close()
        
    try:
        logger.debug('Deleting, and re-creating settings.yaml.')
        os.remove('./settings.yaml')
        with open('./settings.yaml', mode='w') as file:
            yaml.dump(config, file)
            file.close()
        logger.info('Updated settings file.')
        logger.info('Please restart the application!')
        exit(0)

    except Exception as e:
        logger.error(f'Unable to update settings file: {e}')
        exit(1)
    
def update_database(conn=sql_connection()):
    # Update Users Table
    username = 'potatoe'
    mod = 1
    subscriber = 1
    turbo = 1
    msg = 13
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?, ? ,? ,?)", (username, mod, subscriber, turbo, msg))
    conn.commit()
    # Update Messages Table
            
    # Commit to the database
            
    # Read table
    cursor.execute("SELECT * from users WHERE moderator == 1")   
    print(cursor.fetchone())


if __name__ == '__main__': 
    config = read_yaml()
    #chat_tracker(server=config['server'], port=config['port'], nickname=config['nickname'], secret=config['oauth_secret'], channel=config['channel'])
    get_auth_token()