
"""quick script to easily adjust the file that contains the changing-times for the heater.
For simplicity, it presumes that the changing-times are present in the right format (dict, times/keys and values), and in the right chronical order."""

#import ast

# todo: dÄnnerungen nach an dAction-logdatei man?? (mat open/append)  --> brauch ech wuel net, well dZäiten all metternuecht geloggt gin? (oh, awer just dei fier deen dag...) - mee wann ech load-timesdata man...?

earlywake = "06:30"
latewake = "07:30"
earlysleep = "21:20"  # war 21:40
latesleep = "22:00"  # war 22:20  # hänkt awer natierlech och vun der (baussen)temperatur of ...

"""with open("data_times.txt", "r") as readfile:
    dictstarted = False
    dictstr = ""
    for singleline in readfile.readlines():
        if singleline.startswith("{"):
            dictstarted = True
        if dictstarted == True:
            dictstr += singleline
    #print(dictstr)

readdict = ast.literal_eval(dictstr)"""
defaultdict = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}, 6: {}, 7: {}}

newdict = {}

for daydict in defaultdict:
    newdict[daydict] = {}
    # todo: iwwerschr./nei schr. as wuel dat einfachst...? (anstatt auszetauschen, falls dat fier dKeys iwwerhapt geet...)
    if daydict in (1, 2, 3, 4):
        # Monday to Thursday
        newdict[daydict][earlywake] = "normal"
        newdict[daydict][earlysleep] = "reduced"
    elif daydict == 5:
        # Friday
        newdict[daydict][earlywake] = "normal"
        newdict[daydict][latesleep] = "reduced"
    elif daydict == 6:
        # Saturday
        newdict[daydict][latewake] = "normal"
        newdict[daydict][latesleep] = "reduced"
    elif daydict == 7:
        # Sunday
        newdict[daydict][latewake] = "normal"
        newdict[daydict][earlysleep] = "reduced"

print(newdict)

newdictstr = ""
for singledict in newdict:
    newdictstr += f"{str(singledict)}: {newdict[singledict]},\n"
newdictstr = "{" + newdictstr[:-2] + "}"  # newdictstr sliced so that the last 2 characters aren't included, as it's an enter and a comma
#print("newdictstr:", newdictstr)

with open("data_times.txt", "w") as writefile:
    writefile.write("""# Add/Change here the times when the boiler should change his state\n# 1 stands for monday, 2 for tuesday etc.\n# Format-Bsp.:\n'''{1: {"06:30": "normal", "21:40": "reduced"}, 2: {"06:30": "normal", "21:40": "reduced"}, 
    3: {"06:30": "normal", "21:40": "reduced"}, 4: {"06:30": "normal", "21:40": "reduced"}, 
    5: {"06:30": "normal", "22:20": "reduced"}, 6: {"07:30": "normal", "22:20": "reduced"}, 
    7: {"07:30": "normal", "21:40": "reduced"}}'''\n\n""" + newdictstr)  # + f"\n{newdict}
