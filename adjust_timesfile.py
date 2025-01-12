
"""quick script to easily adjust the file that contains the changing-times for the boiler.
For simplicity, it presumes that the changing-times are present in the right format (dict, times/keys and values)."""


earlywake = "06:30"
latewake = "07:30"
earlysleep = "21:20"
latesleep = "22:00"


defaultdict = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}, 6: {}, 7: {}}

newdict = {}

for daydict in defaultdict:
    newdict[daydict] = {}
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
    7: {"07:30": "normal", "21:40": "reduced"}}'''\n\n""" + newdictstr)
