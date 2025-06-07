# Englewood Little Cinema - Raspberry Pi Video Player
#    Copyright (C) 2025 Jim Taggart
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import RPi.GPIO as GPIO
import os
import sys
from subprocess import Popen, PIPE, call
import time
from threading import Lock
import signal
import argparse
import pigpio

# Initialize pigpio for PWM control
pi = pigpio.pi()
lastpress = time.time()

# House lights control (12v mosfet)
LIGHT_PIN = 18
LIGHT_MIN = 12
LIGHT_MAX = 255

# Video playback state
current_video = 0
video_count = 0
state = 0  # current power state of the display
screen_toggle = 1  # toggle the screen or not, 0 is not
sleep_wait = 0.1  # Time delay for how long to hold a button press

class _GpioParser(argparse.Action):
    """ Parse a GPIO spec string """
    def __call__(self, parser, namespace, values, option_string=None):
        gpio_dict = {}
        pin_pairs = values.split(',')
        for pair in pin_pairs:
            pair_split = pair.split(':')

            if 0 == len(pair_split) > 2:
                raise ValueError('Invalid GPIO pin format')

            try:
                in_pin = int(pair_split[0])
            except ValueError:
                raise ValueError('GPIO input pin must be numeric integer')

            try:
                out_pin = int(pair_split[1])
            except ValueError:
                raise ValueError('GPIO output pin must be numeric integer')
            except IndexError:
                out_pin = None

            if in_pin in gpio_dict:
                raise ValueError('Duplicate GPIO input pin: {}'.format(in_pin))

            gpio_dict[in_pin] = out_pin

        setattr(namespace, self.dest, gpio_dict)

class VideoPlayer(object):
    _GPIO_BOUNCE_TIME = 200
    _VIDEO_EXTS = ('.mp4', '.m4v', '.mov', '.avi', '.mkv')
    _GPIO_PIN_DEFAULT = {
        26: 21  # Single button setup
    }

    # Use this lock to avoid multiple button presses updating the player
    # state simultaneously
    _mutex = Lock()

    # The currently playing video filename
    _active_vid = None

    # The process of the active video player
    _p = None

    def __init__(self, audio='hdmi', autostart=True, restart_on_press=False,
                 video_dir=None, gpio_pins=None, loop=True,
                 no_osd=False, shutdown_pin=None, splash=None, debug=False):
        if debug is False:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")

        global video_count
        
        # Use default GPIO pins, if needed
        if gpio_pins is None:
            gpio_pins = self._GPIO_PIN_DEFAULT.copy()
        self.gpio_pins = gpio_pins

        # Add shutdown pin
        self.shutdown_pin = shutdown_pin

        # Assemble the list of videos to play
        self.videos = [os.path.join(video_dir, f)
                      for f in sorted(os.listdir(video_dir))
                      if os.path.splitext(f)[1] in self._VIDEO_EXTS]
        if not self.videos:
            raise Exception('No videos found in "{}". Please specify a different '
                          'directory or filename(s).'.format(video_dir))

        video_count = len(self.videos)
        self.debug = debug

        assert audio in ('hdmi', 'local', 'both'), "Invalid audio choice"
        self.audio = audio

        self.autostart = autostart
        self.restart_on_press = restart_on_press
        self.loop = loop
        self.no_osd = no_osd
        self.splash = splash
        self._splashproc = None

    def _kill_process(self):
        """ Kill a video player process. SIGINT seems to work best. """
        if self._p is not None:
            os.killpg(os.getpgid(self._p.pid), signal.SIGINT)
            self._p = None

    def switch_vid(self, pin):
        """ Switch to the next video in sequence """
        global state
        global current_video
        global video_count
        global lastpress

        # Only allow button presses every 4 seconds to avoid multiple videos
        if time.time() > lastpress + 4:
            lastpress = time.time()
            
            # Use a mutex lock to avoid race condition when
            # multiple buttons are pressed quickly
            with self._mutex:
                filename = self.videos[current_video]
                current_video = (current_video + 1) % video_count
                
                # Kill any existing video process
                self._kill_process()
                
                # Start the new video
                cmd = ['omxplayer']
                if self.audio == 'hdmi':
                    cmd.append('--adev hdmi')
                elif self.audio == 'local':
                    cmd.append('--adev local')
                if self.no_osd:
                    cmd.append('--no-osd')
                cmd.append(filename)
                
                self._p = Popen(cmd, stdout=PIPE, stderr=PIPE,
                              preexec_fn=os.setsid)
                self._active_vid = filename

                # Dim the house lights
                for p in range(LIGHT_MAX, LIGHT_MIN, -1):
                    pi.set_PWM_dutycycle(LIGHT_PIN, p)
                    time.sleep(0.013)

    @property
    def in_pins(self):
        """ Create a tuple of input pins, for easy access """
        return tuple(self.gpio_pins.keys())

    def start(self):
        global pi
        global state

        # Fade in the house lights
        if not state:
            for p in range(LIGHT_MIN, LIGHT_MAX):
                pi.set_PWM_dutycycle(LIGHT_PIN, p)
                time.sleep(0.013)

        # Clear the screen on startup
        os.system('clear')
        print("\033c")

        if not self.debug:
            # Clear the screen
            os.system('clear')
            # Disable the (blinking) cursor
            os.system('tput civis')

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)

        if screen_toggle:  # turn off the screen after boot
            os.system("vcgencmd display_power 0")

        for in_pin, out_pin in self.gpio_pins.items():
            GPIO.setup(in_pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

        # Set up the shutdown pin
        if self.shutdown_pin:
            GPIO.setup(self.shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(self.shutdown_pin,
                                GPIO.FALLING,
                                callback=lambda _: call(['shutdown', '-h', 'now'], shell=False),
                                bouncetime=self._GPIO_BOUNCE_TIME)

        if self.autostart:
            if self.splash is not None:
                self._splashproc = Popen(['fbi', '--noverbose', '-a',
                                        self.splash])
            else:
                # Start playing first video
                self.switch_vid(self.in_pins[0])

        # Enable event detection on each input pin
        for pin in self.in_pins:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=self.switch_vid,
                                bouncetime=self._GPIO_BOUNCE_TIME)

        # Loop forever
        try:
            while True:
                time.sleep(0.5)
                if not self.loop:
                    pid = -1
                    if self._p:
                        pid = self._p.pid
                        self._p.communicate()
                    if self._p:
                        if self._p.pid == pid:
                            self._active_vid = None
                            self._p = None
                            if state == 1:  # turn the screen off when we are done
                                if screen_toggle:
                                    os.system("vcgencmd display_power 0")
                                state = 0
                                os.system('clear')
                                print("\033c")
                                # Bring up the house lights
                                for p in range(LIGHT_MIN, LIGHT_MAX, 1):
                                    pi.set_PWM_dutycycle(LIGHT_PIN, p)
                                    time.sleep(0.013)

        except KeyboardInterrupt:
            pass
        finally:
            self.__del__()

    def __del__(self):
        if not self.debug:
            # Reset the terminal cursor to normal
            os.system('tput cnorm')

        # Cleanup the GPIO pins (reset them)
        GPIO.cleanup()

        # Kill any active video process
        self._kill_process()

        # Kill any active splash screen
        if self._splashproc:
            os.killpg(os.getpgid(self._splashproc.pid), signal.SIGKILL)

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Englewood Little Cinema - Raspberry Pi Video Player

This program is designed to power a looping video display, where the active
video can be changed by pressing a button (i.e. by shorting a GPIO pin).
The active video can optionally be indicated by an LED (one output for each
input pin; works well with switches with built-in LEDs, but separate LEDs work
too).

This video player uses omxplayer, a hardware-accelerated video player for the
Raspberry Pi, which must be installed separately.
"""
    )
    parser.add_argument('--audio', default='hdmi',
                      choices=('hdmi', 'local', 'both'),
                      help='Output audio over HDMI, local (headphone jack),'
                           'or both')
    parser.add_argument('--no-autostart', action='store_false',
                      dest='autostart', default=True,
                      help='Don\'t start playing a video on startup')
    parser.add_argument('--no-loop', action='store_false', default=True,
                      dest='loop', help='Don\'t loop the active video')
    parser.add_argument(
        '--restart-on-press', action='store_true', default=False,
        help='If True, restart the current video if the button for the active '
             'video is pressed. If False, pressing the button for the active '
             'video will be ignored.')
    parser.add_argument(
        '--video-dir', default=os.getcwd(),
        help='Directory containing video files.')
    parser.add_argument('--gpio-pins', default=VideoPlayer._GPIO_PIN_DEFAULT,
                      action=_GpioParser,
                      help='List of GPIO pins. Either INPUT:OUTPUT pairs, or '
                           'just INPUT pins (no output), separated by '
                           'commas.')
    parser.add_argument('--debug', action='store_true', default=False,
                      help='Debug mode (don\'t clear screen or suppress '
                           'terminal output)')
    parser.add_argument('--countdown', type=int, default=0,
                      help='Add a countdown before start (time in seconds)')
    parser.add_argument('--splash', type=str, default=None,
                      help='Splash screen image to show when no video is '
                           'playing')
    parser.add_argument('--no-osd', action='store_true', default=False,
                      help='Don\'t show on-screen display when changing '
                           'videos')
    parser.add_argument('--shutdown-pin', type=int, default=None,
                      help='GPIO pin to trigger system shutdown (default None)')

    # Invoke the videoplayer
    args = parser.parse_args()

    # Apply any countdown
    countdown = args.countdown

    while countdown > 0:
        sys.stdout.write(
            '\rEnglewood Little Cinema starting in {} seconds '
            '(Ctrl-C to abort)...'.format(countdown))
        sys.stdout.flush()
        time.sleep(1)
        countdown -= 1

    del args.countdown

    VideoPlayer(**vars(args)).start()

if __name__ == '__main__':
    main()
