
# kivy-label with white (very light grey) background

from kivy.app import Builder
from kivy.uix.label import Label

Builder.load_string("""
<MyWhiteLabel>:
    font_size: 20
    #background_color: 1, 1, 1, 1
    #background_normal: ""
    canvas.before:
        Color:
            rgba: 1, 1, 1, 0.7
        #Line:    # --- adds a border --- #
        #    width: 2
        #    rectangle: self.x, self.y, self.width, self.height
        Rectangle: 
            size: self.width, self.height
            pos: self.x, self.y
            
<MyWarnLabel>:
    font_size: 20
    #background_color: 1, 1, 1, 1
    #background_normal: ""
    canvas.before:
        Color:
            rgba: 0, 0, 0, 0.9  # 1, 1, 1, 0.7
        #Line:    # --- adds a border --- #
        #    width: 2
        #    rectangle: self.x, self.y, self.width, self.height
        Rectangle: 
            size: self.width, self.height
            pos: self.x, self.y
            """)

class MyWhiteLabel(Label):
    pass

class MyWarnLabel(Label):
    pass
