import pifacecad

cad = pifacecad.PiFaceCAD()    # create PiFace Control and Display object
cad.lcd.backlight_off()         # turns the backlight on
cad.lcd.cursor_off()
cad.lcd.blink_off()
cad.lcd.write("SLEEPING...zzzzz\nWaking up at 8am") # writes hello world on to the LCD
