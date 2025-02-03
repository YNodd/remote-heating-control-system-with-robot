

"""
Code to control a heating system remotely by a robot, which presses the corresponding buttons on the boiler (Viessmann
Vitodens 200-W).
 
The graphical user interface is created with Kivy, and can be used with mouse or touch. 
In our case, a Raspberry Pi acts as a server on which the application runs.

To use the program, we have set our boiler permanently to reduced state (which we have set to ca. 8° C), and we deleted
all saved changing times in the boiler. Then we raise or reduce the temperature by choosing (or turning off) the  boiler's
own feature "länger warm" (longer warm) - with the buttons in the GUI or automatically with saved changing times, who
control the robot that pushes the boiler buttons.
(The longer warm feature of the boiler originally is meant to prolongate the heating time in the evening, but on this
type of boiler, it also raises to normal state when no times for changing are saved).

Some features of the program are: raising or reducing spontaneously, automatic changing times and vacation dates,
changing the schedule once to holiday times with a single button press.

Please consider:
- when the program is started, the user has to ensure that the state of the program and the state of the boiler are 
identical (for example by setting the boiler state manually).
- if the state of the program is 'none', because there was a problem with loading the data for the changing times, the 
file has to be corrected and the program restarted.
- not every "weird" combination of actions is being taken care of by the code, as it was created for use by ourselves,
and not for a typical end user. Comments in the code refer to those "problems" that I was aware of and didn't handle.
- to use more than 2 states (reduced or normal) or to use the program with another boiler type, the code has to
be adjusted.
- the code is written for a boiler with 1 heating circuit ('Heizkreis'). To use more circuits, the code has to been adapted.
- The methods of the class Heizung (and the commands transmitted to the robot for a specific action), depend heavily on
the interface of the boiler at hand (what possibilities/commands the boiler itself provides).
"""


import socket
import logging
from datetime import datetime, timedelta
import copy
import ast
import re
import os

# the following is needed because otherwise (with KIVY_LOG_MODE = "KIVY"), kivy will affect all logs, even of third-party
#   modules, and for example the module "logging" will not write to a file as expected:
os.environ['KIVY_LOG_MODE'] = 'MIXED'  # needs to be done before the import of kivy!

from kivy.config import Config
# everything here must be above all the other imports:
Config.set("graphics", "position", "custom")  # position must be set to "custom" (here that way or manually in the kivy configuration file), otherwise it doesn't work
Config.set("graphics", "left", 0)  # coordinate system
Config.set("graphics", "top", 0)
Config.set("graphics", "height", 430)  # 445
Config.set("graphics", "width", 795)  # 800
#Config.set("graphics", "allow_screensaver", True)  # more on kivy configurations: https://kivy.org/doc/stable/api-kivy.config.html#module-kivy.config, but doesn't work

import kivy
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout

from kivy.clock import Clock

from ownlabel import MyWarnLabel  # own module with custom kivy-label (it's a label that tells the user to wait while actions run)

kivy.require('2.1.0')

errorlogfile = "LOG_heiz_fehler.txt"
actionlogfilei = "LOG_heiz_action.txt"
urlaubfile = "data_urlaub.txt"
timesfile = "data_times.txt"

datetimeformat = "%Y-%m-%d %H:%M"
timeformat = "%H:%M"

default_changetimes = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}, 6: {}, 7: {}}  # default dictionary for the automatic changes per day

robot_ip = "192.168.178.33"
testrobot_ip = "192.168.178.32"  # test-IP (with fake-robot that answers as if the messages/commands would have been carried out)
myrobot_ip = robot_ip  # TODO: change to robot_ip / testrobot_ip for normal use or for use with fake-robot
myrobot_port = 23

versionnr = "1.3"
testerei = False  # test status, doesn't write to logfiles if True (only outputs lots of debugging messages)
zeiten_testerei = False  # to test time related actions, with custom method that fakes elapsing time
onlyerrorlog = False  # log errors vs. errors and actions

if zeiten_testerei == True:
    testzeit = "23:58"  # choose here the starttime to test time related actions
if testerei == True:  # for test-modus (logging debug modus, no writing to log-files)
    # the debug-modus doesn't log into a file, it's more similar to print-statement to debug:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s -  %(levelname)s -  %(message)s', datefmt = "%Y-%m-%d %H:%M")
else:  # so no testing, but log errors (and possibly actions):
    errorlogger = logging.getLogger("errorlog")
    errorhandler = logging.FileHandler(errorlogfile)
    errorformatter = logging.Formatter('\n%(asctime)s %(levelname)s | %(name)s | %(message)s', datefmt = "%d-%m-%Y %H:%M:%S")
    errorhandler.setFormatter(errorformatter)
    errorlogger.addHandler(errorhandler)
    actionlogger = logging.getLogger("actionlog")
    actionlogger.setLevel(logging.DEBUG)
    actionhandler = logging.FileHandler(actionlogfilei)
    actionformatter = logging.Formatter('%(asctime)s %(levelname)s | %(name)s | %(message)s', datefmt = "%d-%m-%Y %H:%M:%S")
    actionhandler.setFormatter(actionformatter)  # schema: '31-10-2024 09:33:35 INFO | actionlog | lo rof gedréckt.'
    actionlogger.addHandler(actionhandler)

#logging.debug('the debug-logging part starts here:')
#logging.debug(f"time_now: {datetime.now().strftime('%H:%M')}")


class Robot():
    """for the communication with the robot
    (by calling the class Heizung (via the user interface), who calls the robot).
    The server for the communication runs on the robot."""

    def __init__(self, robot_ip, communication_port):
        self.robot_ip = robot_ip
        self.communication_port = communication_port

    def send_message(self, message_text):
        """Sends the message to the robot (create a client/socket, send the message, check the response).
        Returns True if the message is successfully sent, otherwise it returns a string describing the problem (to be
        able to show the problem in the window/GUI.
        The parameter is a string containing the command for the robot, for example a sequence of numbers that represent
        the buttons of the boiler that the robot should push, separated by spaces (Bsp: "1 4 4 4.").
        Every command ends with a dot to mark the end of the message."""
        logging.debug("robot-method send_message activated")

        socket_on = False

        # create a socket / connection to the robot:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # if the IP for connecting doesn't exist, connect() throws quickly an error (z.B.: OSError 113), but if it exists and doesn't
            #   respond, the method connect() would try connecting until it's own timeout. To keep it short, set own timeout:
            s.settimeout(5)
            # pass the IP-address that should be called to the connect-method:
            s.connect((self.robot_ip, self.communication_port))
            socket_on = True
        except TimeoutError:
            logging.exception("timeouterror while connecting")
            if testerei == False:
                errorlogger.exception("timeout while trying to connect the socket")
            return "timeouterror"
        except OSError:
            # possible OSErrors (among others): OSError: [Errno 113] No route to host (robot doesn't answer)
            #   OSError: [Errno 101] Network is unreachable (the LAN cable is not plugged in / there is no WLAN connection)
            #   ConnectionRefusedError: [Errno 111] Connection refused
            #   TimeoutError: [Errno 110] Connection timed out
            logging.exception("problem with the communication/connection!")
            if testerei == False:
                errorlogger.exception("Problem mat der Kommunikatioun! (Verbindung)")
            return "Verbindungsproblem"
        except:  # for the case there were another error than OSError
            logging.exception("undefined except reached while trying connecting to robot")
            if testerei == False:
                errorlogger.exception("Allgemengen except agesprong bei Konnektioun")
            return "Verbindungsproblem - allg. except agespr.!!"

        if socket_on == True:  # checks if the socket exists/was created
            s.send(message_text.encode())

            try:
                if message_text == "test.":
                    s.settimeout(7)
                elif message_text == "1 3 3 4 4 4 2 4 4 1 1 2 2 4 4 4 4.":
                    s.settimeout(18)
                else:
                    s.settimeout(15)

                answer = s.recv(1024)

            except (TimeoutError, socket.timeout):
                logging.exception("Timeout-Error!")
                if testerei == False:
                    errorlogger.exception("Timeout!")
                return "Timeout"
            except:  # for the case there were another error than TimeoutError
                logging.exception("general except thrown while evaluating the message")
                if testerei == False:
                    errorlogger.exception("Allgemengen except agesprong beim Auswerten vum Message")
                return "allgem. except agesprongen bei Message-Auswertung!!"

            finally: # close the socket (this block runs even if there is a return in the except-blocks above)
                s.close()

            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"'{message_text}' geschéckt")

            # compare the robot answer with the original sent text - the answer should be the repetition of the
            #   command (to make sure the communication worked):
            if answer.decode() != message_text:
                reckmeldung = f"Kommunikatiounsfehler! Message-Text war: {message_text}\nÄntwert/Echo as: {answer.decode()}"
                logging.debug(reckmeldung)
                if testerei == False:
                    errorlogger.error(reckmeldung)
                return "Echo-Text falsch"
            #else:
            #    reckmeldung = f"Dat huet geklappt!. De mesage war: {message_text}"
            #    logging.debug(reckmeldung)

            return True


class Heizung():
    """This class is the heating control system itself.
    The methods of the class Heizung (and which commands they have to transmit to the robot for a specific command/result),
    depend heavily on the interface of the boiler at hand - what can be programmed and what is programmed, and the
    inherent logic of how the interface is to be used (means what possibilities/commands it provides).

    Here, the boiler itself is set to the reduced state, with no times saved for changing automatically.
    All the automatic changes are then done in this class, by activating and deactivating the boiler-feature 'länger warm',
    which raises the temperature to normal.
    For vacation setting, the boiler is turned off (runs on frost protection) by choosing 'Heizkreis aus' in the boiler control."""

    def __init__(self):
        self.myrobot = Robot(myrobot_ip, myrobot_port)
        self.status = "none"  # possible values: "normal", "reduziert", "urlaub" # (shouldn't be type None, as the value None for a kivy-label could break the code)
        self.longerwarm_on = False  # helper variable to ensure the longerwarm-button cannot be pressed if it already is active
        self.tomorrowholiday_on = False
        self.newmorningtime = None  # new change-time if the morning data has to be changed because of holiday

        self.zeit = datetime.now().strftime("%H:%M")
        if zeiten_testerei == True:
            self.zeit = testzeit
        self.weekday = datetime.now().isoweekday()
        #logging.debug(f"current day of the week is: {self.weekday}")
        # helper variables to ensure that the automatic changes don't try to run as often as they are called by the kivy scheduler (e.g. 60 times in a minute):
        self.alreadyrun_times = False
        self.alreadyrun_holiday = False

        self.communicationworks = self.myrobot.send_message("test.")  # test on start if the communication with the robot works
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"Kommunikatiounstest get zréck: {self.communicationworks}")

        # reading the file with the holiday-times and load the dictionary:
        read_urlaub_dict = self.load_urlaubdata()
        if type(read_urlaub_dict) == dict:
            self.urlaub_times = read_urlaub_dict
        else:
            self.urlaub_times = {}  # load an empty dict when there was a problem with loading it from file (to prevent a traceback when trying to iterate)
        logging.debug(f"self.urlaub_times in the Heizung init: {self.urlaub_times}")

        # reading the file with the automatic changing-times for the different weekdays:
        read_times_dict = self.load_timesdata()
        if read_times_dict == False:
            self.change_times = copy.deepcopy(default_changetimes)  # load a default dictionary (an empty nested dictionary)
        else: # dictionary in the right format (either "empty" or with data)
            self.change_times = read_times_dict
        logging.debug(f"self.change_times in the Heizung init: {self.change_times}")

        # create a dict with the automatic change-times for the current day (that is a copy of the corresponding sub-dict):
        self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])
        logging.debug(f"changetimes_today for weekday {self.weekday}: {self.changetimes_today}")

        # identify the status for the start:
        returned_status = self.read_timesstatus()
        if returned_status != False:
            self.status = returned_status
        else:
            logging.error("checking the status with the changetimes returns False!")
            if testerei == False:
                errorlogger.error("status-ofchecken mat den changetimes get False!")

        # log the start-status:
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"den status beim Starten as: {self.status}")


    def load_timesdata(self):
        """loads the times (when the state of the boiler has to be automatically changed), from an external file.
        So the change-times can be edited in the file and loaded into the program during the runtime of the app.
        Returns either a nested dictionary (with data or empty), or False.
        (the file contents are not checked for coherence, for example there could be a missing day/dict, or a day/number
        could be double - a missing daynumber could break the code when the dictionary is searched for the given weekdayday)."""
        if os.path.exists(timesfile):  # checks if the file already exists
            with open(timesfile, "r") as timefile:
                readfile = timefile.read()
                # extract the changetimes-dictionary from the file:
                #   (the file contains a multi-line string as a format example, so regex is used to extract the "real" changing-times dictionary)
                cleanedreadfile = re.sub(r"'''[\s\S]*'''", '', readfile)  # Remove multi-line comments
                cleanedreadfile = re.sub(r'#.*', '', cleanedreadfile)  # Remove single-line comments
                cleanedreadfile = re.sub(r"\s*\n\s*\n\s*", '', cleanedreadfile)  # remove whitespaces etc

                # convert the retrieved dictionary-string to a dictionary object:
                if len(cleanedreadfile) != 0:
                    try:
                        loadedtimesdata = ast.literal_eval(cleanedreadfile)  # ast.literal_eval() is able to build a python dictionary from a string
                    except (SyntaxError, ValueError):
                        logging.exception("Problem with loading timesdata (SyntaxError or ValueError)")
                        if testerei == False and onlyerrorlog == False:
                            errorlogger.exception("Problem beim Ausliesen vun der Zäiten-Datei - falscht Format an der Datei")
                        return False
                    except:
                        logging.exception("General except reached while reading the times file!")
                        if testerei == False:
                            errorlogger.exception("Allgemengen except agesprong beim Zäiten-Ausliesen!")
                        return False

                    # check the dictionary for correctness:
                    if type(loadedtimesdata) == dict:
                        # check the values of the (nested) dictionary:
                        for singledictname in loadedtimesdata:  # looping through the nested dictionary
                            # check the names of the sub-dictionaries:
                            if singledictname not in [1, 2, 3, 4, 5, 6, 7]:
                                logging.debug(f"false dictname: {singledictname}")
                                if testerei == False:
                                    errorlogger.error(f'Problem with a dicionary name - has to be 0-7 and not {singledictname}')
                                return False
                            for singlekey in loadedtimesdata[singledictname]:
                                subdict = loadedtimesdata[singledictname]
                                # check the correctness of the values in the sub-dictionaries:
                                if subdict[singlekey] not in ["reduziert", "normal"]:
                                    logging.debug(f"False value: {subdict[singlekey]}")
                                    if testerei == False:
                                        errorlogger.error(f'Problem with a value - has to be "reduziert" or "normal" and not {subdict[singlekey]}')
                                    return False
                                # check the correctness of the dates/keys of the sub-dictionaries:
                                try:
                                    if len(singlekey) == 5:  # check if it is "06:30" and not "6:30" (which would be accepted as a valid time, but crash the app)
                                        datetime.strptime(singlekey, timeformat)
                                    else:
                                        # force the except block to run (as it's an incorrect timeformat too)
                                        raise ValueError
                                except:
                                    logging.debug("There is a problem with the time-format in timesdata")
                                    if testerei == False:
                                        errorlogger.exception(f"there is a problem with the formatting of the time in timesdata. It is: {singlekey} but should be: {timeformat}")
                                    return False
                        return loadedtimesdata
                    else: # (no dict)
                        logging.debug("Doesn't result in a dictionary type")
                        if testerei == False:
                            errorlogger.error("Problem with loading the timesdata - the result is not a dict")
                        return False
                else:  # if the length of the file is 0 / the file is empty
                    return default_changetimes  # (and not just {}, as it can bring problems later on because of KeyErrors)
        else:  # if the file doesn't exist
            writefile = open(timesfile, "x")  # "x" only creates a new file, if it doesn't already exist (whereas "w" would overwrite an existing file)
            writefile.write("""# Add/Change here the times when the boiler should change his state\n# 1 stands for Monday, 2 for Tuesday etc.\n# Format-Bsp.:\n'''{1: {"06:30": "normal", "21:40": "reduziert"}, 2: {"06:30": "normal", "21:40": "reduziert"}, 
    3: {"06:30": "normal", "21:40": "reduziert"}, 4: {"06:30": "normal", "21:40": "reduziert"}, 
    5: {"06:30": "normal", "22:20": "reduziert"}, 6: {"07:30": "normal", "22:20": "reduziert"}, 
    7: {"07:30": "normal", "21:40": "reduziert"}}'''""")
            writefile.close()
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"Datei fier Zäiten-Daten {timesfile} ugeluet")
            return default_changetimes

    def load_urlaubdata(self):
        """loads the dates and times for holiday from an external file. So the holiday-times can be edited in the file and
        loaded into the program during the runtime of the app.
        The file should only contain 1 dictionary (one line of relevant data, besides of the comments/format example).
        Returns either a dictionary (with data or empty), or False.
        (the file contents are not checked for coherence, for example the holiday-end could lie earlier than the start)"""

        # check if the file exists:
        if os.path.exists(urlaubfile):
            with open(urlaubfile, "r") as readurlaubfile:
                readfile = readurlaubfile.read()
                # extract the holiday-dictionary from the file (ignore the lines preceeded by a hashtag, as they are comments):
                cleanedurlaubfile = re.sub(r'#.*', '', readfile)  # Remove single-line comments
                cleanedurlaubfile = re.sub(r"\s*\n\s*\n\s*", '', cleanedurlaubfile)  # remove whitespaces etc
                if len(cleanedurlaubfile) == 0:
                    logging.debug("urlaub-file is empty")
                    if testerei == False:
                        errorlogger.error("urlaub-Datei as eidel - keng Vakanz agin")
                    return {}
                else: # len(cleanedurlaubfile) != 0:
                    # make a dictionary from the dict-like string in the file:
                    try:
                        urlaubdict = ast.literal_eval(cleanedurlaubfile)
                    except (SyntaxError, ValueError):  # if the string in the file has not the right format for a dict
                        logging.exception("Problem with urlaubdata! (SyntaxError or ValueError)")
                        if testerei == False:
                            errorlogger.exception("Problem mam Format vun urlaubdata")
                        return False
                    except:
                        logging.exception("Reached general except while reading holiday data!!")
                        if testerei == False:
                            errorlogger.exception("Allgemengen except agesprong beim Ausliesen vun urlaubdata!!")
                        return False

                    for singlekey in urlaubdict:
                        # check the correctness of the values:
                        if urlaubdict[singlekey] not in ["normal", "urlaub"]:
                            logging.debug(f"The values of the urlaub-data have to be 'normal' or 'urlaub'!")
                            if testerei == False:
                                errorlogger.error(f"The values of the urlaub-data can only be 'normal' or 'urlaub', and not {urlaubdict[singlekey]}")
                            return False
                        # check the correctness of the date-formats:
                        try:
                            if len(singlekey) == 16:  # ensure date/time are in the correct format (and not for example 2025-1-29 4:30)
                                datetime.strptime(singlekey, datetimeformat)
                            else:
                                raise
                        except:
                            logging.debug("There is a problem with the date format")
                            if testerei == False:
                                errorlogger.exception(f"There is a problem with the formatting of the date/time. It is: {singlekey} but should be: {datetimeformat}")
                            return False
                    return urlaubdict
        else:
            writefile = open(urlaubfile, 'x')  # create urlaub-file if it doesn't exists
            # write a comment to the file:
            writefile.write("# The format (for holiday on and off) should be: {'datum': 'urlaub', 'datum': 'normal'}\n# and the format for date and time 'YYYY-MM-DD HH:MM', z.B. 2024-11-12 13:41\n# Bsp: {'2024-11-13 10:00': 'urlaub', '2024-11-13 12:00': 'normal'}")
            writefile.close()
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"Datei fier urlaubs-daten {urlaubfile} ugeluet")
            urlaubdict = {}
            return urlaubdict

    def read_timesstatus(self):
        """Checks what status it is (should be) based on the change-times and the current time, and returns it (or False,
        if the changetimes for today have just 0 or 1 element)."""

        # create a sorted list of the keys (times of the day) from the change_times dict to get the sequence of the change-times (z.B. ['06:45', '22:15']):
        self.changetimes_list = sorted([key for key in self.changetimes_today])
        if len(self.changetimes_list) > 1: # (time-strings can be compared with < and >)
            if self.zeit < self.changetimes_list[0] or self.zeit > self.changetimes_list[-1]:  # if it lies before the first or after the last changetime
                # (if the current time is smaller/earlier than the lowest, the status has to be the one from the night (stated by
                #   the last index in the sorted list) - presuming the status is the same for the night on every weekday)
                status_tobe = self.changetimes_today[self.changetimes_list[-1]]
            else:
                # loop through changetimes_list and find the first value that is greater than the current time, then chose the status of the value that lies before:
                for i in range(len(self.changetimes_list)):
                    if self.zeit < self.changetimes_list[i]:  # changetimes_list[i] refers to the key/status-values in the dictionary
                        # the needed heating-status is the one that lies before the chosen/greater time:
                        assigned_time = self.changetimes_list[i-1]
                        status_tobe = self.changetimes_today[assigned_time]  # find the corresponding status in the dict
                        break # otherwise the last corresponding time would be chosen instead of the first (if more than one corresponds)
                    elif self.zeit == self.changetimes_list[i]:
                        # if the current time is exactly the time where the status should change
                        assigned_time = self.changetimes_list[i]
                        status_tobe = self.changetimes_today[assigned_time]
            return status_tobe
        else:
            logging.debug("The changetimes_list for today has 1 or fewer entries, the status can't be determined!")
            if testerei == False:
                errorlogger.error("changetimes_list fier haut huet maximal 1 Antrag! - et sin also keng normal Heizungs-Zäiten agedro (an den Start-status as net ermettelbar)")
            return False

    def refresh_heiz_time(self):
        self.zeit = datetime.now().strftime('%H:%M')

    def refresh_urlaub(self):
        """Refreshes the attribute urlaub_times, and passes the return value from load_urlaubdata to the GUI-class (where
        refresh_urlaub is called when the associated button is pressed) so that it can be shown in the window.
        It returns either False or a dictionary (empty or with data)"""
        urlaub_request = self.load_urlaubdata()  # gets a dict (empty or with data) or False
        if urlaub_request == False:
            self.urlaub_times = {}
            return False
        else:  # urlaub_request is {} or a normal dict
            self.urlaub_times = urlaub_request
            return urlaub_request

    def refresh_changetimes(self):
        """Refreshes the attributes change_times and changetimes_today.
        Returns either False or a dictionary ("empty" or with data) to the GUI class (where it is called), so that it can be
        shown in the window.

        The time data cannot be loaded while the feature tomorrow-holiday is active, because the loaded times would
        overwrite the altered changetimes for that day. To load the changetimes from file, the user has to deactivate
        the tomorrow-holiday, then load the data from file (and reactivate the holiday-feature, if needed)."""

        if self.tomorrowholiday_on == False:

            times_request = self.load_timesdata()
            if times_request == False:  # error in the times-file
                # ensure that there exists at least an empty dict, to avoid tracebacks because of KeyErrors:
                self.change_times = copy.deepcopy(default_changetimes)
                self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])
                #logging.debug(f"self.changetimes_today for today: {self.changetimes_today}")
                return False
            elif times_request == default_changetimes:  # the "empty" (nested) dict default_changetimes
                if testerei == False:
                    errorlogger.error("timesdata as eidel")
                return "empty"
            else:  # times_request is a normal dict
                self.change_times = times_request
                self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])
                #logging.debug(f"self.changetimes_today for today: {self.changetimes_today}")
                logging.debug(f"timesdata loaded. timesdata returns: {times_request}.\n change_times is now: {self.change_times}")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"timesdata ragelueden.\n change_times as lo: {self.change_times}")

                # define what status it has to be according to the times-file, and adjust it if needed:
                status_tobe = self.read_timesstatus()
                if self.status == "normal" and status_tobe == "reduziert":
                    if testerei == False and onlyerrorlog == False:
                        actionlogger.info("automatesch Status-Upassung decideiert (weinst Zäiten-Aktualiseirung)")
                    return "reduce now"
                elif self.status == "reduziert" and status_tobe == "normal":
                    if testerei == False and onlyerrorlog == False:
                        actionlogger.info("automatesch Status-Upassung decideiert (weinst Zäiten-Aktualiseirung)")
                    return "raise now"
                elif self.status == "none":
                    # when status is 'none' (for ex. because there where no valid changing-times while starting the app),
                    #   the current status can't be determined because the change/direction is not clear. In this case keep
                    #   "none" so that it's obvious that something went wrong. (Can only be fixed by correcting the problem
                    #   and restarting the app).
                    logging.debug("The status is 'none' - so the current target status cannot be determined/set!")
                    if testerei == False:
                        errorlogger.error("Den Heizungsstatus as 'none' - deen aktuellen soll-status kann also net ermettelt/agestallt gin!")
                    return "status was none"

                return True

        else:
            logging.debug("tomorrow-holiday is active - timesdata cannot be loaded")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"D'Zäiten konnten net agelies gin, well muar-Feierdag aktiv as.")
            return "muar-Feierdag"


    def check_heiz_statusandactions(self):
        """called regularly by the kivy-scheduler to check if the status label in the GUI has to be refreshed, and
        additionally checks if any time-related action has to be taken. If it is the moment to automatically
        change the boiler to another state, the corresponding methods are called."""

        # if shortly after midnight, refresh the weekday and other attributes:
        if self.zeit == "00:01":
            if self.weekday != datetime.now().isoweekday():  # ensure the midnight-change is executed only once per day (and not as often as the method is called while it's "00:01"):
                self.longerwarm_on = False
                self.weekday = datetime.now().isoweekday()  # refresh for the new day
                self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])  # new changing times for the new day
                if self.tomorrowholiday_on == True:  # if the new day is a holiday, its first change-time is reset to the raise-time of Saturday
                    if testerei == False and onlyerrorlog == False:
                        actionlogger.info("Den Dag haut huet Feierdags-Zäiten")
                    self.changetimes_list = sorted([x for x in self.changetimes_today])
                    oldmorning = self.changetimes_list[0]
                    self.changetimes_today.pop(oldmorning)  # delete the old morning change-time from the dict
                    self.changetimes_today[self.newmorningtime] = "normal"  # add the new morning data to the dict
                    self.newmorningtime = None  # reset the helper variables
                    self.tomorrowholiday_on = False
                logging.debug(f"changetimes_today for weekday {self.weekday}: {self.changetimes_today}, status: {self.status}, longerwarm_on: {self.longerwarm_on}")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"changetimes_today for weekday {self.weekday}: {self.changetimes_today}, status: {self.status}, longerwarm_on: {self.longerwarm_on}")

        # CHECK HOLIDAY:
        # if the current date and time are in the dictionary of the holiday settings, the status has to be changed to "urlaub" (or back to "normal"):
        current_datetime = datetime.now().strftime(datetimeformat)
        if current_datetime in self.urlaub_times and self.alreadyrun_holiday == False:
            urlaub_changeto = self.urlaub_times[current_datetime]  # "urlaub" or "normal"
            #logging.debug("variable urlaub_changeto has been created")
            #logging.debug(f"change_to: {urlaub_changeto}")
            self.alreadyrun_holiday = True  # mark that the change runs for the first time, to avoid repetitions
            # ensure that the status hasn't been already reset:
            if (urlaub_changeto == "urlaub" and self.status == "normal") or (urlaub_changeto == "urlaub" and self.status == "reduziert"):
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info("Automatesch Aktioun (Vakanz aschalten) decidéiert")
                response_urlaub_on = self.turn_vacation_on()
                return response_urlaub_on
            elif urlaub_changeto == "urlaub" and self.status == "none":
                if testerei == False:
                    errorlogger.error("De status war 'none', wéi urlaub hätt sollen agestallt gin!")
                return False
            elif urlaub_changeto == "normal" and self.status == "urlaub":  # ensure that the status hasn't been already reset
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info("Automatesch Aktioun (vakanz ausschalten) decidéiert")
                response_urlaub_off = self.turn_vacation_off()
                return response_urlaub_off
            else: # (none of the status values that exist at the moment. Also "none", when changing-times are missing)
                logging.debug("status was probably 'none', or a new status-value was added without changing the code appropriately - The 'else' was started during check holiday in check_heiz_statusandactions()")
                if testerei == False:
                    errorlogger.error(f"Status war wuel 'none' beim urlaub-ofchecken? Oder du hues een status bäigemat ouni de Code unzepassen? (else agesprong beim urlaub-ofchecken, an der check_heiz_statusandactions) / urlaub_changeto as: {urlaub_changeto}, status as: {self.status}")
                return False
        # reset the helper variable self.alreadyrun_holiday as soon as it isn't needed anymore (when the time/minute has changed):
        if self.alreadyrun_holiday == True and current_datetime not in self.urlaub_times:
            # (this handling could be a problem if there are 2 consecutive times in the list - this isn't covered because such a use would make no sense)
            self.alreadyrun_holiday = False

        # CHECK CHANGE-TIMES:
        # if the current time is present in the dictionary of time changes, we have to change to the corresponding state:
        if self.status != "urlaub":  # during holiday, these changes have to be blocked
            if self.zeit in self.changetimes_today and self.alreadyrun_times == False:
                change_to = self.changetimes_today[self.zeit]  # check what state is needed according to the dict
                #logging.debug("variable change_to as ugelued gin")
                #logging.debug(f"change_to: {change_to}")
                self.alreadyrun_times = True # mark that the change runs for the first time, to avoid repetitions
                if change_to == "reduziert":
                    #self.reduce_now()  # if the command reduce_now is called from here, it works, but there is no "please wait"-popup
                    if testerei  == False and onlyerrorlog == False:
                        actionlogger.info("Automatesch Aktioun (reduce now) decidéiert")
                    return "reduce now"  # this return passes the command through to the class KivyGui, and triggers the appropriate button there
                elif change_to == "normal":
                    #self.raise_now()
                    if testerei  == False and onlyerrorlog == False:
                        actionlogger.info("Automatesch Aktioun (raise now) decidéiert")
                    return "raise now"
                else: # (none of the status values that exist at the moment)
                    logging.debug("The 'else' was started during check change-times in check_heiz_statusandactions(). Maybe a new status-value was added without changing the code appropriately??")
                    if testerei == False:
                        errorlogger.error(f"Du hues wuel een status bäigemat ouni de Code unzepassen? (else agesprong beim times-ofchecken, an der check_heiz_statusandactions) / change_to as: {change_to}, status as: {self.status}")
                    return False
        # reset the helper variable self.alreadyrun_times as soon as it isn't needed anymore (when the time/minute has changed)
        if self.alreadyrun_times == True and self.zeit not in self.changetimes_today:
            # (this handling could be a problem if there are 2 consecutive times in the list - this isn't covered because such a use would make no sense)
            self.alreadyrun_times = False


    def turn_vacation_on(self):
        """Turns vacation mode on by selecting the boiler mode 'Heizkreis aus' which sets the boiler to a frost protection state.
        It assumes that there is only one 'Heizkreis' (heating circuit) used.
        Returns a string to be displayed in the GUI."""
        logging.debug("method turn_vacation_on activated")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungsmethod turn_vacation_on agesprong")
        urlaub_message = "1 3 3 4 4 4 3 4 4."
        robotaction = self.myrobot.send_message(urlaub_message)
        logging.debug(f"self.myrobot.send_message(urlaub_message) returned {robotaction}")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"De Roboter get zréck: {robotaction}")
        if robotaction == True:
            self.status = "urlaub"
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"Vakanze-status aktivéiert, de status as lo: {self.status}")
            return "Vakanz ageschalt"
        else:
            logging.debug("There has been a problem with the activation of the holiday status")
            if testerei == False:
                errorlogger.error(f"Problem mam Roffueren fier d'Vakanz - d'Roboter-Method get zréck: {robotaction}")
            return "Problem mam Roffueren fier d'Vakanz!"

    def turn_vacation_off(self):
        """Turns vacation mode off by setting the boiler on again. It sets 'Heizkreis ein' and 'länger warm',
        assuming that you want to have the boiler on normal temperature after vacation raise (ignoring the automatic time
        settings at that moment - but automatic changes are re-enabled so that the next change will take place).
        Returns a string to be displayed in the GUI."""
        logging.debug("method turn_vacation_off activated")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungsmethod turn_vacation_off agesprong")
        urlauboff_message = "1 3 3 4 4 4 2 4 4 1 1 2 2 4 4 4 4."
        robotaction = self.myrobot.send_message(urlauboff_message)
        logging.debug(f"self.myrobot.send_message(urlauboff_message) returned {robotaction}")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"De Roboter get zréck: {robotaction}")
        if robotaction == True:
            self.status = "normal"
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"'urlaub' ausgeschalt. De Status as lo: {self.status}")
            logging.debug(f"The status is now: {self.status}")
            return "Vakanz ausgeschalt"
        else:
            logging.debug("There has been a problem with the DEactivation of the holiday status")
            if testerei == False:
                errorlogger.error(f"Problem mam Ropfueren no der Vakanz - d'Roboter-Method get zréck: {robotaction}")
            return f"Problem mam Ropfueren no der Vakanz! D'Roboter-Method get zréck: {robotaction}"



    def reduce_now(self):
        """Reduces the temperature immediately (if the status was normal). For example, before you leave for the day or
        when you go to bed earlier.
        Sends the message to the robot.
        Uses the "länger warm" (longer warm) mode of the heating. This stays until it is changed again.
        Passes the return value of the robot method to the GUI.
        When longer-warm was active, it is turned off when the status is changed to reduced or holiday."""
        logging.debug("method reduce_now activated")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungsmethod reduce_now agesprong")
        if self.status != "reduziert" and self.status != "urlaub":  # (like self.status == normal, but works also if there would be more than 3 status-values)
            rof_message = "1 4 4 4 4."
            robot_action = self.myrobot.send_message(rof_message)
            logging.debug(f"self.myrobot.send_message(rof_message) returned {robot_action}")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"De Roboter get zréck: {robot_action}")
            if robot_action == True:
                self.status = "reduziert"
                logging.debug(f"The status is now: {self.status}")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"De status as lo: {self.status}")
                # ensure that "longer-warm" cannot be active when the status was reduced or put to 'urlaub', because it wouldn't make any sense:
                if self.longerwarm_on == True:
                    self.longerwarm_on = False
            return robot_action
        else:
            logging.debug("The status 'reduziert' was already on, or the status was 'urlaub'")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info("Näischt gemat - war schon 'reduziert' (oder de status war 'urlaub')")
            return "Näischt gemat"


    def raise_now(self):
        """raises the temperature if it was reduced, by sending the message to the robot. Works with the mode
        'länger warm' of the boiler.
        Stays until changed (automatically or by pressing a button)."""
        logging.debug("method raise_now activated")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungsmethod raise_now agesprong")
        # if status is reduced and needs to raise to normal, the raise-message is sent to the robot:
        if self.status != "normal" and self.status != "urlaub":
            rop_message = "1 4 4 4 4."
            robot_action = self.myrobot.send_message(rop_message)
            logging.debug(f"self.myrobot.send_message(rop_message) returned {robot_action}")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"De Roboter get zréck: {robot_action}")
            if robot_action == True:
                self.status = "normal"
                logging.debug(f"The status is now: {self.status}")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"De Status as lo: {self.status}")
            return robot_action
        else:
            logging.debug("The boiler was already raised or 'urlaub'/holiday is on")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info("Näischt gemat - war schon rop (oder 'urlaub' as an)")
            return "Näischt gemat"


    def longer_warm(self):
        """Switches off the evening reducing (by deleting the last changing-schedule of the day from the dictionary
        changetimes_today - presuming that there are at least 2 change-times per day and that the last automatic action
        on a given day always is a reducing of the temperature).
        To do this, a sorted list of the keys (times of the day) is created from changetimes_today to get the sequence
        of the change-times (z.B. ['06:45', '22:15']). With the help of the current changetimess_list, the method
        longer_warm can find/remove the last changing time of the day.

        This means, the heater heats through the night, if it isn't reduced. It would then reduce again the day later
        when a reducing is scheduled in the times-dictionary.
        It is reset automatically if the status is changed by the method reduce_now to 'reduziert' or 'urlaub'.
        When longer-warm is on and you want to lower the temperature again, you can simply press the reduce-button.

        Isn't possible when tomorrow-holiday is active."""
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungs-method longer_warm agesprong")

        if self.tomorrowholiday_on == False:

            if self.status != "urlaub" and self.longerwarm_on == False: # longer_warm is not already on, and holiday-status neither
                self.changetimes_list = sorted([x for x in self.changetimes_today])  # an up-to-date list is needed for the method longer_warm to find the last changing time
                if len(self.changetimes_list) > 0:  # not empty
                    if len(self.changetimes_list) >= 2:
                        # ensure that longer_warm can not be used after the last reducing of the day, nor when it was reduced manually:
                        if self.zeit < self.changetimes_list[-1] and self.status != "reduziert":
                            last_reducetime = self.changetimes_list[-1]  # supposing the last planned action in a day is always a reducing
                            # refresh the times-dictionary for today:
                            deleted_reducetime = self.changetimes_today.pop(last_reducetime)
                            #print("deleted_reducetime:", deleted_reducetime)  # to return also the value: key, value = dictname.popitem(keyname)
                            #logging.debug(f"self.changetimes_today: {self.changetimes_today}")
                            self.longerwarm_on = True
                            return True
                        else: # the current time lies after the last reducing-time of the day, longer_warm makes no sense here, or the status was already reduced manually
                            logging.debug("It's already after the evening-reducing (or was manually reduced)!")
                            if testerei == False and onlyerrorlog == False:
                                actionlogger.info("War schon no der Owes-Ofsenkung (oder manuell reduzéiert)")
                            return "Näischt gemat"
                    else:
                        # supposing that there should be at least 2 change-times per day to make sense (and to have an evening-reducing):
                        logging.debug("changetimes_list has fewer than 2 elements!")
                        if testerei == False:
                            errorlogger.error("changetimes_list huet manner wéi 2 Elementer!")
                        return "changetimes_list has fewer than 2 elements!"
                else:
                    logging.debug("changetimes_list for today is empty/faulty")
                    if testerei == False:
                            errorlogger.error("changetimes_list fier haut as eidel/fehlerhaft!")
                    return "Zäiten-Lescht as eidel oder fehlerhaft"
            else:  # # longerwarm_on is True or status is "urlaub"
                logging.debug("longer_warm was already active, or it is during holiday-status")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info("longer_warm war schon an, oder et war 'urlaub' an")
                return "Näischt gemat"

        else:  # tomorrowholiday_on is True
            logging.debug("tomorrow_holiday is active, longer_warm can't be set")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info("longer_warm kann net agemat gin well dFeierdags-Astellung aktiv as")
            return "muar-Feierdag as aktiv, länger-warm as net méiglech!"

    def longer_warm_back(self):
        """Sets off the longer-warm. This means, that the normal change-times for the day are loaded again."""
        if self.longerwarm_on == True:
            self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])  # resets the changing-times to standard
            self.longerwarm_on = False
            return True
        else:
            logging.debug("longer_warm wasn't active")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info("longer_warm war net an")
            return "Näischt gemat"


    def tomorrow_holiday(self):
        """Used if the next day is a holiday.
        Resets the automatic changing times for the evening and the following morning, going to bed late the evening and
        waking late the other morning (which are the same values as the ones of day 6 (Saturday).
        To see the chosen times, push the button again.

        The combination of tomorrow_holiday and longer_warm is not possible, as it doesn't make much sense (and longer_warm_back
        would reset the original changing times for the weekday at hand and would therefore overwrite the tomorrow-holiday-times).
        To change from tomorrow_holiday to longer_warm, the holiday-feature has first to be disabled."""
        logging.debug("method tomorrow_holiday started")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungs-method tomorrow_holiday agesprong")

        # if longer_warm is active, there is no evening reducing time in the current times that could be updated:
        if self.longerwarm_on == False:
            # if it wasn't already activated (and there are saved change_times in the file):
            if self.tomorrowholiday_on == False and len(self.changetimes_list) != 0:
                # change the evening reducing of the current day to the late reducing time from Saturday:
                self.changetimes_list = sorted(x for x in self.changetimes_today) # make a sorted list of the dictionary keys (current day)
                oldeveningtime = self.changetimes_list[-1]  # get the last change-time for today
                saturdaylist = sorted(x for x in self.change_times[6])  # create a sorted list of the Saturday change-times
                neweveningtime = saturdaylist[-1]  # last changing time on Saturday
                self.changetimes_today.pop(oldeveningtime)  # delete change-time from the current changetimes-dict
                self.changetimes_today[neweveningtime] = "reduziert"  # add the new reducing time to the dict
                # set tomorrow_holiday_on to True (to be able to adjust the automatic times for the next day during midnight changes):
                self.tomorrowholiday_on = True
                self.newmorningtime =  saturdaylist[0]  # first changing time on Saturday
                logging.debug(f"Method tomorrow_holiday activated. New change-times for today: {self.changetimes_today}")
                return True
            else:  # self.tomorrowholiday_on is True
                logging.debug("Done nothing - tomorrow_holiday was already active")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"Näischt gemat (muar-Feierdag war schon an - d'Zäiten sin: {self.changetimes_today})")
                return f"Näischt gemat - d'Zäiten sin: {self.changetimes_today}"
        else:  # longer warm is active
            logging.debug("Done nothing - longer_warm is active")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info(f"länger warm as an! (Näischt gemat)")
            return "länger warm as an - muar-Feierdag kann net gemat gin!"

    def tomorrow_holiday_back(self):
        """Undo the feature tomorrow-holiday (resets the changing-times to the standard values)."""
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungs-Method tomorrow_holiday_back agesprong")
        if self.tomorrowholiday_on == True:
            self.changetimes_today = copy.deepcopy(self.change_times[self.weekday])
            self.tomorrowholiday_on = False
            return True
        else:
            logging.debug("tomorrow_holiday wasn't active")
            if testerei == False and onlyerrorlog == False:
                actionlogger.info("muar-Feierdag war net an")
            return "Näischt gemat"

    def test_robot(self):
        """Method to check/move the robot, with a sequence that does nothing (doesn't change the configurations in the
        boiler at hand)"""
        logging.debug("Method test_robot activated")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info("Heizungsmethod test_robot agesprong")
        test_message = "1 3 2 4 1 1."
        #if testerei == True:
        #    test_message = "13 2 4 1 1."
        robot_action = self.myrobot.send_message(test_message)
        logging.debug(f"self.myrobot.send_message(test_message) returned {robot_action}")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"self.myrobot.send_message(test_message) returned {robot_action}")
        return robot_action



class KivyGui(App):
    """gets called in the class Interface(), and calls itself the methods of the class Heizung that are needed.
    Creates the graphical interface with Kivy."""

    def __init__(self):
        super(KivyGui, self).__init__()
        self.myheizung = Heizung()
        logging.debug("init of the class KivyGui activated")

    # to build the application we have to return a widget on the build() function:
    def build(self):
        layout = FloatLayout()
        self.title = f"Heizungssteierung V {versionnr}"  # window title

        # BUTTON ACTIONS:

        def popup_on(nobutton_assigned):
            """to activate the popup-label ("Please wait"), when a button is pressed"""
            layout.add_widget(lbpopup)
        def popup_off(nobutton_assigned):
            """to deactivate the popup-label ("Please wait")"""
            layout.remove_widget(lbpopup)

        def set_raise_now(currentbutton):
            """action bound to the raise-now-button btnrop"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response = self.myheizung.raise_now()
            popup_off(currentbutton)
            lboutput.text = f"Roboter/Kommunikatioun get zréck: {response}"
            #if onlyerrorlog == False and testerei == False:
            #    actionlogger.info(f"Roboter/Kommunikatioun get zréck: {response}")

        def set_reduce_now(currentbutton):
            """action bound to the reduce-now-button btnrof"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response = self.myheizung.reduce_now()
            popup_off(currentbutton)
            lboutput.text = f"Roboter/Kommunikatioun get zréck: {response}"
            #if onlyerrorlog == False and testerei == False:
            #    actionlogger.info(f"Roboter/Kommunikatioun get zréck: {response}")

        def set_longer_warm(currentbutton):
            """action bound to the longer-warm-button btnsetlonger"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            # call the method of Heizung that makes the needed changes to not reduce the temp in the evening:
            response_longer = self.myheizung.longer_warm()
            if response_longer == True:
                lboutput.text = f"nei Zäiten fier haut: {self.myheizung.changetimes_today}"
                lblongerwarm.text = "länger warm an"
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"nei Zäiten fier haut: {self.myheizung.changetimes_today}")
            else:
                lboutput.text = response_longer

        def set_longer_warm_back(currentbutton):
            """action bound to the undo-longer-warm-button btnsetlongerback"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response_longerback = self.myheizung.longer_warm_back()
            if response_longerback == True:
                lboutput.text = f"nei Zäiten fier haut: {self.myheizung.changetimes_today}"
                lblongerwarm.text = ""
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"nei Zäiten fier haut: {self.myheizung.changetimes_today}")
            else:
                lboutput.text = response_longerback

        def set_tomorrow_holiday(currentbutton):
            """action bound to the tomorrow-holiday-button btnholiday"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response_tomorrow = self.myheizung.tomorrow_holiday()  # returns True, "länger warm as an!" or "Näischt gemat"
            if response_tomorrow == True:
                lboutput.text = f"muar-Feierdag as aktivéiert. Nei Zäiten fier haut: {self.myheizung.changetimes_today}"
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(lboutput.text)
            else:
                lboutput.text = response_tomorrow

        def set_tomorrow_holiday_back(currentbutton):
            """action bound to the undo-tomorrow-holiday-button btnholidayback"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response_tomorrowback = self.myheizung.tomorrow_holiday_back()
            if response_tomorrowback == True:
                lboutput.text = f"muar-Feierdag as rem ausgeschalt. Zäiten fier haut: {self.myheizung.changetimes_today}"
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(lboutput.text)
            else:
                lboutput.text = response_tomorrowback

        def get_holidaydata(currentbutton):
            """when the associated button is pushed, it calls the methods to load the automatic holiday changes from the file"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response_urlaub = self.myheizung.refresh_urlaub()  # returns False or a dict (either empty or with data)
            if response_urlaub == False:
                lboutput.text = "Problem mat der Datei/Formateirung vun urlaubdata!"
                logging.debug(lboutput.text)
                if testerei == False:
                    errorlogger.error(lboutput.text)
            elif response_urlaub == {}:
                lboutput.text = "urlaubdata as eidel!"
                logging.debug(lboutput.text)
                if testerei == False:
                    errorlogger.error(lboutput.text)
            else:  # it's the right, non-empty dict
                lboutput.text = f"urlaubdata get zréck: {response_urlaub}"
                logging.debug(f"urlaubdata loaded. urlaubdata returns: {response_urlaub}. urlaub_times is now: {self.myheizung.urlaub_times}")
                if testerei == False and onlyerrorlog == False:
                    actionlogger.info(f"urlaubdata ragelueden. urlaubdata get zréck: {response_urlaub}. urlaub_times as lo: {self.myheizung.urlaub_times}")

        def get_timedata(currentbutton):
            """when the associated button is pushed, it calls the methods to load the automatic status-changing times from the file"""
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response_times = self.myheizung.refresh_changetimes()  # returns False or an "empty" dict or normal dict
            if response_times == False:
                lboutput.text = "Problem mat der Datei/Formateirung vun timesdata!"
                logging.debug(lboutput.text)
                #if testerei == False:
                #    errorlogger.error(lboutput.text)
            elif response_times == "empty":  # default_changetimes is an "empty" nested dict
                lboutput.text = "timesdata as eidel!"
                logging.debug(lboutput.text)
                #if testerei == False:
                #    errorlogger.error(lboutput.text)
            elif response_times == "muar-Feierdag":
                lboutput.text = f"muar-Feierdag as aktiv - d'Zäiten kennen net agelies gin."
                logging.debug(lboutput.text)
            else: # it is the right dict/format
                lboutput.text = f"timesdata as ragelueden gin / Fier haut as: {self.myheizung.changetimes_today}"
                #logging.debug(f"timesdata loaded. timesdata returns: {response_times}.\n change_times is now: {self.myheizung.change_times}")
                #if testerei == False and onlyerrorlog == False:
                #    actionlogger.info(f"timesdata ragelueden. timesdata get zréck: {response_times}.\n change_times as lo: {self.myheizung.change_times}")

                # automatic adjustments based on new timesdata, when necessary:
                if response_times == "reduce now":
                    btnrof.trigger_action()  # this is like pushing the button btnrof (carried out this way so that the please-wait-label appears)
                elif response_times == "raise now":
                    btnrop.trigger_action()  # this is like pushing the button btnrop (carried out this way so that the please-wait-label appears)
                elif response_times == "status was none":
                    lboutput.text = "PROBLEM BEIM UPASSEN UN DEI NEI TIMESDATA! (de status war 'none')"


        def call_robottest(currentbutton):
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            response = self.myheizung.test_robot()
            popup_off(currentbutton)
            lboutput.text = f"Roboter/Kommunikatioun get zréck: {response}"
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(lboutput.text)

        def test_robocommunication(currentbutton):
            logging.debug(f"'{currentbutton.text}' pushed")
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(f"'{currentbutton.text}' gedréckt")
            commresponse = self.myheizung.myrobot.send_message("test.")
            popup_off(currentbutton)
            lboutput.text = f"Roboter/Kommunikatioun get zréck: {commresponse}"
            if onlyerrorlog == False and testerei == False:
                actionlogger.info(lboutput.text)


        def refresh_kivy_time(nobutton_assigned):
            # refresh the clock of the class Heizung (by calling the own method of the class Heizung):
            self.myheizung.refresh_heiz_time()
            # refresh the clock label in the GUI (otherwise the first time from the starting would remain without being updated):
            lbclock.text = self.myheizung.zeit


        def check_kivy_statusandactions(nobutton_assigned):
            """refreshes the indicators of status and longerwarm_on in the GUI.
            If the Heizung.check_heiz_statusandactions() method returns that a status has to be automatically changed
            because of time settings, the correspondent button is triggered here in the KivyGui (it is done this way and
            not by calling the robot directly from the class Heizung as the button-trigger implies that the please-wait-label
            appears in the GUI)."""
            heizstatus_response = self.myheizung.check_heiz_statusandactions()
            lbstatus.text = f"status: {self.myheizung.status}"
            if self.myheizung.longerwarm_on == False:
                lblongerwarm.text = ""

            # automatic adjustments based on time, when necessary:
            if heizstatus_response == "reduce now":
                btnrof.trigger_action()  # this is like pushing the button btnrof (carried out this way so that the please-wait-label appears)
            elif heizstatus_response == "raise now":
                btnrop.trigger_action()  # this is like pushing the button btnrop
            elif heizstatus_response == False:
                lboutput.text = "PROBLEM BEIM AUTOMATESCHEN EMSCHALTEN vun Zäiten/urlaub! (ev. war de status 'none'?)"
            elif heizstatus_response != None:  # example: "Vakanz ageschalt" (holiday activated)
                lboutput.text  = f"Roboter/Kommunikatioun get zréck: {heizstatus_response}"


        def test_statuschanging(nobutton_assigned):
            """function to change the time arbitrarily to test methods which rely on time (e.g. when the status
            should change and be displayed in the GUI). The minutes are incremented to mimic a normal time elapsing/changing.
            The desired starting time has to be set where the function is called (as it has to be outside of the
            function to not set the time to start with every function call).
            (Isn't needed anymore since the implementation of the time data from the files, as now change-times can be
            easily changed in the time-file during runtime for testing)."""
            logging.debug("Fonctioun test_statuschanging as agesprong")
            if type(self.myheizung.zeit) != str:
                print("self.myheizung.zeit:", self.myheizung.zeit.strftime("%H:%M"))  # only print the hours and minutes
            elif type(self.myheizung.zeit) == str:
                print("self.myheizung.zeit:", self.myheizung.zeit)
                self.myheizung.zeit = datetime.strptime(self.myheizung.zeit, "%H:%M")  # it has to be a datetime object to be able to add 1 minute
            self.myheizung.zeit +=  timedelta(minutes = 1)
            self.myheizung.zeit = self.myheizung.zeit.strftime("%H:%M")  # change again the time to string for the rest of the program and for displaying
            lbclock.text = self.myheizung.zeit


        # SCHEDULES / PRESENT READINGS:
        if zeiten_testerei == False:
            # refresh the clock regularly (calls refresh_kivy_time(), which refreshes the clock label in the window and the zeit-attribute of the class Heizung):
            Clock.schedule_interval(refresh_kivy_time, 1)  # (timeout is in seconds)
            # check the status of the heizung and if actions have to be taken:
            Clock.schedule_interval(check_kivy_statusandactions, 1)
        # to test if the status of the class Heizung changes as it should on given times of the day:
        else: # (if zeiten_testerei == True)
            returned_status = self.myheizung.read_timesstatus()
            if returned_status != False:
                self.myheizung.status = returned_status
            else:
                logging.error("status-ofchecken mat den changetimes get False!")
            Clock.schedule_interval(test_statuschanging, 5)  # This is basically a replacement for the time update for testing (so that I can use the times I need for the test)
            Clock.schedule_interval(check_kivy_statusandactions, 5)  # check the status of Heizung regularly


        # BUTTONS AND LABELS:

        # (size_hint = (width-percent, height-percent))  # size_hint should be used with pos_hint (and not pos) to allow the elements to find their places when the window is resized
        # (pos = (sideways, bottom-top)  # starts at the bottom left corner with 0,0 (for the top left corner you need e.g. (0, 500))
        # (pos_hint = )  # position of the elements by percentage, Bsp: pos_hint={'center_x': .5, 'center_y': .5})

        # clock-Label:
        lbclock = Label(text = str(datetime.now().strftime("%H:%M")), font_size = 20, color = "blue",  size_hint = (0.8, .2), pos_hint={'center_x': .85, 'center_y': .95})
        layout.add_widget(lbclock)

        # status-label:
        lbstatus = Label(text = f"status: {self.myheizung.status}", font_size = 20, color = "blue",  size_hint = (0.2, .2), pos_hint={'center_x': .15, 'center_y': .95})
        layout.add_widget(lbstatus)

        # longer-warm-label:
        lblongerwarm = Label(text = "", font_size = 20, color = "blue", size_hint = (0.2, 0.2), pos_hint={'center_x': .15, 'center_y': .90})
        layout.add_widget(lblongerwarm)

        # output-label (messages for the user):
        lboutput = Label(size_hint = (0.85, .2), pos_hint={'center_x': .50, 'center_y': .20})
        # start message - show in the GUI if the communication works (gets overwritten when other actions are taken):
        lboutput.text = f"Kommunikatioun funzt?: {self.myheizung.communicationworks}"
        layout.add_widget(lboutput)

        # raise-button:
        btnrop = Button(text ='lo rop', size_hint =(.4, .23), pos_hint={'center_x': .25, 'center_y': .75})
        btnrop.bind(on_press = popup_on, on_release=set_raise_now)
        layout.add_widget(btnrop)

        # reduce-button:
        btnrof = Button(text ='lo rof', size_hint =(.4, .23), pos_hint={'center_x': .75, 'center_y': .75})
        btnrof.bind(on_press = popup_on, on_release= set_reduce_now)
        layout.add_widget(btnrof)

        # button for heating longer:
        btnsetlonger = Button(text = "länger warm an", size_hint = (.30, .12), pos_hint={'center_x': .25, 'center_y': .43})
        btnsetlonger.bind(on_press = set_longer_warm) # (on_press = popup_on, on_release= set_longer_warm) isn't needed for the please-wait-label because the robot does not need to take an action
        layout.add_widget(btnsetlonger)

        # button to set off heating longer:
        btnsetlongerback = Button(text = "länger warm aus", size_hint = (.30, .12), pos_hint={'center_x': .25, 'center_y': .30})
        btnsetlongerback.bind(on_press = set_longer_warm_back)
        layout.add_widget(btnsetlongerback)

        # button to load the holiday dates and times from the file:
        btnurlaub = Button(text = "load urlaubdata", size_hint = (.30, .12), pos_hint={'center_x': .75, 'center_y': .30})
        btnurlaub.bind(on_press = get_holidaydata)
        layout.add_widget(btnurlaub)

        # button to load the automatic changing times from the file:
        btntimes = Button(text = "load timesdata", size_hint = (.30, .12), pos_hint={'center_x': .75, 'center_y': .43})
        btntimes.bind(on_press = get_timedata)
        layout.add_widget(btntimes)

        # button to set the next day to a holiday:
        btnholiday = Button(text = "muar-Feierdag an", size_hint = (.18, .12), pos_hint = {"center_x": .50, "center_y": .43})
        btnholiday.bind(on_press = set_tomorrow_holiday)
        layout.add_widget(btnholiday)

        # button to set off tomorrow_holiday (reset the day after to a normal day regarding the saved change-times)
        btnholidayback = Button(text = "muar-Feierdag aus", size_hint = (.18, .12), pos_hint = {"center_x": .50, "center_y": .30})
        btnholidayback.bind(on_press = set_tomorrow_holiday_back)
        layout.add_widget(btnholidayback)

        # button to test the function of the robot:
        btntestrobot = Button(text = "test robot", color = "red", size_hint = (0.13, 0.08), pos_hint = {"center_x": .10, "center_y": .10})
        btntestrobot.bind(on_press = popup_on, on_release = call_robottest)
        layout.add_widget(btntestrobot)

        # button to test the communication to the robot:
        btntestcomm = Button(text = "test commun.", color = "red", size_hint = (0.13, 0.08), pos_hint = {"center_x": .24, "center_y": .10})
        btntestcomm.bind(on_press = popup_on, on_release = test_robocommunication)
        layout.add_widget(btntestcomm)

        # please-wait-label (is added in the moment the label is needed (after pressing a button))
        lbpopup = MyWarnLabel(text = "Please wait ...", font_size = 110, color = "red", size_hint = (1, 1)) # pos_hint={'center_x': 1, 'center_y': 1})

        # label that shows that "testerei" (testing state) is True:
        if testerei == True or zeiten_testerei == True:
            lbtesterei = Label(text = "|testerei on|\n|or zeitentest|", color = "pink", font_size = 20, size_hint = (0.25, 0.15), pos_hint = {"center_x": .90, "center_y": .10})
            layout.add_widget(lbtesterei)
        if myrobot_ip != robot_ip:
            lbfakerobot = Label(text = "fake-robot(IP)", color = "pink", font_size = 50, size_hint = (0.25, 0.15), pos_hint = {"center_x": .50, "center_y": .10})
            layout.add_widget(lbfakerobot)

        return layout



class Interface():

    def __init__(self):
        logging.debug(f"init of the class Interface activated (v{versionnr})")
        if testerei == False and onlyerrorlog == False:
            actionlogger.info(f"init vun class Interface agesprong / Programm gestart (Versioun: {versionnr})")

        myKivyGui = KivyGui()
        myKivyGui.run()


#----------------------

my_instanz = Interface()  # this instance later calls all the other classes and methods that are needed

