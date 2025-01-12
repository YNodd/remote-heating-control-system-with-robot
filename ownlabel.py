
# custom kivy labels

from kivy.app import Builder
from kivy.uix.label import Label

Builder.load_string("""
<MyWhiteLabel>:
    font_size: 20
    canvas.before:
        Color:
            rgba: 1, 1, 1, 0.7
        Rectangle: 
            size: self.width, self.height
            pos: self.x, self.y
            
<MyWarnLabel>:
    font_size: 20
    canvas.before:
        Color:
            rgba: 0, 0, 0, 0.9
        Rectangle: 
            size: self.width, self.height
            pos: self.x, self.y
            """)

class MyWhiteLabel(Label):
    # kivy-label with white (very light grey) background
    pass

class MyWarnLabel(Label):
    # label with black background
    pass
