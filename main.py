import logging
import socket
import threading
import yaml
import os
import re
import sqlite3
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
        
if __name__ == "__main__":
    config = read_yaml()
    if config['first_run'] == True:
        init_database()
    update_database(conn=sql_connection())
