
import os
from os.path import expanduser
import logging

def getUsernamePassword():
    home = expanduser("~")
    fileName = home + '/.netrc'
    if not os.path.isfile(fileName):
        logging.debug("ERROR: No .netrc file found in {}".format(home))
        logging.debug("")
        logging.debug("You will need a .netrc file in order to downoad the HyP3 data.")
        logging.debug("Please see the documentation or the webpage https://disc.gsfc.nasa.gov/data-access")
        logging.debug("for information on how to create an Earthdata login and a .netrc file")
        logging.debug("")
        exit(1)
    f = open(fileName,"r")
    username = None
    password = None
    for line in f:
        if "login" in line:
            username = line.split()[1]
            logging.info("Username is {}".format(username))
        if "password" in line:
            password = line.split()[1]
            logging.info("Found password")
    if username is None or password is None:
        logging.error("ERROR: Unable to get username or password from .netrc file")
        exit(1)
    return username, password

