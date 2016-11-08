#!/usr/bin/env python3
# requires `mplayer` to be installed
from time import sleep
import os
import sys
import signal
import shlex
import math
import lirc
import socket
import fcntl
import struct
import urllib.request
import datetime

PY3 = sys.version_info[0] >= 3
if not PY3:
    print("Radio only works with `python3`.")
    sys.exit(1)

from threading import Barrier  # must be using Python 3
import subprocess
import pifacecommon
import pifacecad
from pifacecad.lcd import LCD_WIDTH

WAKEUP_TIME = 8
WEEKDAY_BEDTIME = 23

UPDATE_INTERVAL = 1

STATIONS = [

    {'name': "Purple Radio",
     'source': 'http://stream.purpleradio.co.uk/stream.php',
     'info': None},
    {'name': "BBC Radio 1",
     'source': 'http://www.radiofeeds.co.uk/bbcradio1.pls',
     'info': None},
    {'name': "BBC Radio 2",
     'source': 'http://www.radiofeeds.co.uk/bbcradio2.pls',
     'info': None},
    {'name': "Heart",
     'source': 'http://media-ice.musicradio.com/HeartTyneWearMP3',
     'info': None},
    {'name': "Metro Radio",
     'source': 'http://tx.sharp-stream.com/icecast.php?i=metro.mp3',
     'info': None},
    {'name': "Capital FM",
     'source': 'http://media-ice.musicradio.com/CapitalTyneWearMP3',
     'info': None},
    {'name': "Planet Rock",
     'source': 'http://tx.sharp-stream.com/icecast.php?i=planetrock.mp3',
     'info': None},

]

PLAY_SYMBOL = pifacecad.LCDBitmap(
    [0x10, 0x18, 0x1c, 0x1e, 0x1c, 0x18, 0x10, 0x0])
PAUSE_SYMBOL = pifacecad.LCDBitmap(
    [0x0, 0x1b, 0x1b, 0x1b, 0x1b, 0x1b, 0x0, 0x0])
INFO_SYMBOL = pifacecad.LCDBitmap(
    [0x6, 0x6, 0x0, 0x1e, 0xe, 0xe, 0xe, 0x1f])
MUSIC_SYMBOL = pifacecad.LCDBitmap(
    [0x2, 0x3, 0x2, 0x2, 0xe, 0x1e, 0xc, 0x0])

PLAY_SYMBOL_INDEX = 0
PAUSE_SYMBOL_INDEX = 1
INFO_SYMBOL_INDEX = 2
MUSIC_SYMBOL_INDEX = 3


class Radio(object):
    def __init__(self, cad, start_station=0):
        self.current_station_index = start_station
        self.playing_process = None
        self.timerEnabled = True

        # set up cad
        cad.lcd.blink_off()
        cad.lcd.cursor_off()
        cad.lcd.backlight_on()

        cad.lcd.store_custom_bitmap(PLAY_SYMBOL_INDEX, PLAY_SYMBOL)
        cad.lcd.store_custom_bitmap(PAUSE_SYMBOL_INDEX, PAUSE_SYMBOL)
        cad.lcd.store_custom_bitmap(INFO_SYMBOL_INDEX, INFO_SYMBOL)
        self.cad = cad

    @property
    def current_station(self):
        """Returns the current station dict."""
        return STATIONS[self.current_station_index]

    @property
    def playing(self):
        return self._is_playing

    @playing.setter
    def playing(self, should_play):
        if should_play:
            self.play()
        else:
            self.stop()

    @property
    def text_status(self):
        """Returns a text represenation of the playing status."""
        if self.playing:
            return "Now Playing"
        else:
            return "Stopped"

    def play(self):
        """Plays the current radio station."""
        print("Playing {}.".format(self.current_station['name']))
        # check if is m3u and send -playlist switch to mplayer
        if self.current_station['source'].split("?")[0][-3:] in ['m3u', 'pls']:
            play_command = "mplayer -quiet -playlist {stationsource}".format(
		        stationsource=self.current_station['source'])
        else:
            play_command = "mplayer -quiet {stationsource}".format(
                stationsource=self.current_station['source'])
        self.playing_process = subprocess.Popen(
            play_command,
            #stdout=subprocess.PIPE,
            #stderr=subprocess.PIPE,
            shell=True,
            preexec_fn=os.setsid)
        self._is_playing = True
        self.update_display()

    def stop(self):
        """Stops the current radio station."""
        print("Stopping radio.")
        os.killpg(self.playing_process.pid, signal.SIGTERM)
        self._is_playing = False
        self.update_playing()

    def change_station(self, new_station_index):
        """Change the station index."""
        was_playing = self.playing
        if was_playing:
            self.stop()
        self.current_station_index = new_station_index % len(STATIONS)
        if was_playing:
            self.play()

    def next_station(self, event=None):
        self.change_station(self.current_station_index + 1)

    def previous_station(self, event=None):
        self.change_station(self.current_station_index - 1)

    def update_display(self):
        self.cad.lcd.clear()
        self.update_playing()
        self.update_station()
        # self.update_volume()

    def update_playing(self):
        """Updated the playing status."""
        #message = self.text_status.ljust(LCD_WIDTH-1)
        #self.cad.lcd.write(message)
        if self.playing:
            char_index = PLAY_SYMBOL_INDEX
        else:
            char_index = PAUSE_SYMBOL_INDEX

        self.cad.lcd.set_cursor(0, 0)
        self.cad.lcd.write_custom_bitmap(char_index)

    def update_station(self):
        """Updates the station status."""
        message = str(self.current_station_index + 1) + '/' + str(len(STATIONS)) + ' ' + self.current_station['name']
        self.cad.lcd.set_cursor(1, 0)
        self.cad.lcd.write(message)

    def toggle_playing(self, event=None):
        if self.playing:
            self.stop()
        else:
            self.play()

    def close(self):
        self.stop()
        self.cad.lcd.clear()
        self.cad.lcd.backlight_off()

    def view_mac_address(self, event=None):
        mac = getMAC('eth0')
        self.cad.lcd.clear()
        self.cad.lcd.set_cursor(0, 0)
        self.cad.lcd.write('MAC ADDRESS\n')
        self.cad.lcd.write(mac)
        sleep(5)
        self.cad.lcd.move_left()
        sleep(5)
        self.update_display()

    def view_hostname(self, event=None):
        hostname = socket.gethostname() + '.clients.dur.ac.uk'
        self.cad.lcd.clear()
        self.cad.lcd.set_cursor(0, 0)
        self.cad.lcd.write(hostname[0:16] + '\n')
        self.cad.lcd.write(hostname[16:])
        sleep(5)
        self.update_display()

def radio_preset_switch(event):
    global radio
    radio.change_station(event.pin_num)


def radio_preset_ir(event):
    global radio
    radio.change_station(int(event.ir_code))

def getMAC(interface):
    try:
        str = open('/sys/class/net/' + interface + '/address').read()
    except:
        str = "00:00:00:00:00:00"
    return str[0:17]


if __name__ == "__main__":
    # test for mplayer
    try:
        subprocess.call(["mplayer"], stdout=open('/dev/null'))
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            print(
                "MPlayer was not found, install with "
                "`sudo apt-get install mplayer`")
            sys.exit(1)
        else:
            raise  # Something else went wrong while trying to run `mplayer`

    cad = pifacecad.PiFaceCAD()
    global radio

    start_station_index = 3

    radio = Radio(cad, start_station_index)

    now = datetime.datetime.now()
    today_wakeup = now.replace(hour=WAKEUP_TIME, minute=0, second=0, microsecond=0)

    if(now.weekday() < 4 or now.weekday() == 6): # if Mon-Thurs or Sun
        today_sleep = now.replace(hour=WEEKDAY_BEDTIME, minute=0, second=0, microsecond=0) # don't play after weekday bedtime
        if(now > today_wakeup and now < today_sleep):
            radio.play() #
        else:
            quit()
    else:
        if(now > today_wakeup): # if Fri or Sat and it's after wakeup time, play
            radio.play()
        else:
            quit()

    # listener cannot deactivate itself so we have to wait until it has
    # finished using a barrier.
    global end_barrier
    end_barrier = Barrier(2)

    # wait for button presses
    switchlistener = pifacecad.SwitchEventListener(chip=cad)

    switchlistener.register(0, pifacecad.IODIR_ON, radio.toggle_playing)
    switchlistener.register(1, pifacecad.IODIR_ON, radio.previous_station)
    switchlistener.register(2, pifacecad.IODIR_ON, radio.next_station)
    switchlistener.register(3, pifacecad.IODIR_ON, radio.view_hostname)
    switchlistener.register(4, pifacecad.IODIR_ON, radio.view_mac_address)

    switchlistener.activate()
