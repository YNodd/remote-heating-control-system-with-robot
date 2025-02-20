# remote heating control system with robot (for Viessmann Vitodens 200-W)


# What it is:  
Code to control a heating system remotely by a robot, which presses the corresponding buttons on the boiler (Viessmann Vitodens 200-W, with 3.5" black-and-white screen and 4 touch buttons).
It is controlled by the user from the graphical interface of the program, which is communicating with the robot via LAN (Telnet).<br>
In my case, the program runs on a Raspberry Pi.<br>
The graphical user interface is created with Kivy, and can be used with mouse or touch. 

Some features of the program are: raising or reducing spontaneously, automatic changing times and vacation dates, changing the schedule once to holiday times with a single button press. 

I have written the code of the App with the GUI etc. completely in Python. <br>
The code to control the robot is written in C and was done by a friend - the code and the hardware descriptions will be added later, so that our remote control can be reproduced. 

<video src="https://github.com/YNodd/remote-heating-control-system-with-robot/blob/main/video%20of%20robot%20in%20action.mp4" width="300" />
![robot pushing the button](video of robot in action.mp4)

The robot is controlled via a graphical interface on the Raspberry Pi, and presses the corresponding buttons (the move on the start takes longer to reset the screen to the start screen for sure – in case there would another screen be chosen when starting).

# Why we did it:
I wanted remote control to adjust heating, and more functionalities than the boiler control offers (for example, vacation settings can only be set for entire days without specific start or end times, there's no easy option for a single holiday, and changing the saved time schedules for the whole week needs a lot of button pressing).

Viessmann offers remote control devices, but those don't seem to offer more possibilities than the control on the boiler itself (for example, I wanted to be able to reduce or raise the boiler temperature spontaneously, e.g. if I go to bed earlier than planned).<br>
The company gives no access to a direct boiler API, only to a cloud solution - but I want to run my heating and its controls locally. 

Furthermore, I was in search of a "real" project to practice programming (in contrast to the exercises of programming tutorials, that normally aren't of any further real use).


# How it works:
To use our program, we have set the boiler permanently to reduced state (which we have set to ca. 8° C), and we deleted all saved changing times in the boiler. <br>
Then we raise or reduce the temperature by choosing (or turning off) the boiler's own feature "länger warm" (longer warm) - with the buttons in the GUI or automatically with saved changing times, who control the robot that pushes the boiler buttons.<br>
(The longer warm feature of the boiler originally is meant to prolongate the heating time in the evening, but on this type of boiler, it also raises to normal state when no times for changing are saved).<br>
The vacation feature works by turning the boiler off (to frost protection). 

**Functionalities:** 
- raise now
- reduce now
- saved schedules for automatic changing the boiler state over the day
- saved schedules for automatic adjustment to vacations (with hours and minutes)
- longer warm (no night setback)
- holiday the next day (later to bed, and later raise than on normal weekdays)

The schedules for daily changes and vacations are saved in external files and can be edited and loaded during runtime (easy adjusting for the whole week possible by using a simple script).


# If you want to use the code for yourself:
[This is only the code for the main controlling App - the code and the hardware description for the robot will be coming soon.]

For use with the same (or a very similar) type of boiler control (e.g. Viessmann Vitodens 200-W), the complete setup (main app, robot hardware and robot software) can be used as is.

The code can be run in the terminal, or an executable can be packaged with pyinstaller.

The files with the schedules for automatic changes and vacations are created on the first start of the program in the directory where the app was started (if they don't exist already).<br>
To add or change these schedules, simply update the data in the corresponding file, in the right format (it's the format of a Python dictionary and there is an example on top of the files).

Please consider:
- ensure that the IP-addresses (of the sensors and the computer/Raspberry Pi) are assigned permanently in the network
- when the program is started, the user has to ensure that the state of the program and the state of the boiler are identical (for example by setting the boiler state manually).
- if the state of the program is 'none', because there was a problem with loading the data for the changing times, the file has to be corrected and the program restarted.
- not every "weird" combination of actions is being taken care of by the code, as it was created for use by myself, and not for a typical end user. Comments in the code refer to those "problems" that I was aware of and didn't handle.
- to use more than 2 states (reduced or normal) or to use the program with another boiler type (or the same boiler type but more than 1 heating circuit/'Heizkreis'), the code has to be adjusted.<br><br>

What worked for me:<br>
I created a virtual environment this way:
- open the terminal and type<br>
python3 -m venv path/to/venv (e.g. python3 -m venv /home/ynodd/heatingapp)
- install the needed packages in the venv by typing:<br>
pathtovenv/bin/pip install package_name (e.g. /home/ynodd/heatingapp/bin/pip install kivy)

I packaged the code with pyinstaller this way: 
- open the terminal in the folder where the code is saved (or open the terminal anywhere and go there with the cd keyword)
- type in the terminal:
pyinstaller my_code_to_package.py
- This creates some new files and folders in the folder where the original code is. The executable is found in a subfolder of "dist".


# Weaknesses
- without having access directly to the boiler control nor to a camera/OCR, you can't be sure that everything always works as it should - it would be possible that there's an error message on the boiler display and the heating app can't react because it doesn't know.
- The methods of the class Heizung (and the commands transmitted to the robot for a specific action), depend heavily on the interface of the specific boiler control at hand (what possibilities/commands the boiler itself provides). 
- the graphical interface is just a draft that should only ensure that the app works and is easy to use. Design/optical matters were not yet taken into account.


# Used hardware and software

For the main app of the heating control:<br>
Python version 3.11<br>
Kivy version 2.2.1<br>
Raspberry Pi 4 with Debian GNU/Linux 11 (bullseye)<br>
4.3" touchscreen (DSI)<br>

For the robot:<br>
coming soon!


# Warning:
The "fingers" of the robot must be build in a way that they can't injure a person/child.

Additionally, it has to be ensured that they can't damage the buttons or display by pressing too hard.


Use at own risk.