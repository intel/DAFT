# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
# Author Simo Kuusela <simo.kuusela@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

from time import sleep
import os.path

from aft.logger import Logger as logger
from aft.kb_emulators.kb_emulator import KeyboardEmulator

class GadgetKeyboard(KeyboardEmulator):
    '''
    Keyboard emulator class which has methods for sending key strokes through
    usb port using Linux g_hid module.
    '''

    # Empty message which will be sent to stop any keys being pressed
    empty = "\x00\x00\x00\x00\x00\x00\x00\x00"

    # HID keyboard hex codes for modifier keys
    modifier_codes = {
        "CONTROL_L":  0x01, "SHIFT_L":    0x02, "ALT_L":            0x04,
        "SUPER_L":    0x08, "MULTI":      0x08, "CONTROL_R":        0x10,
        "SHIFT_R":    0x20, "MENU":       0x80, "ISO_LEVEL3_SHIFT": 0x40,
        }

    # HID keyboard hex codes for specific keys
    key_codes = {
        # Function keys
        'F1': 0x3A,  'F2': 0x3B,  'F3': 0x3C,  'F4': 0x3D,
        'F5': 0x3E,  'F6': 0x3F,  'F7': 0x40,  'F8': 0x41,
        'F9': 0x42, 'F10': 0x43, 'F11': 0x44, 'F12': 0x45,

        # Symbols above the row of numbers
        '!':  0x1E, '@':  0x1F, '#':  0x20, '$':  0x21, '%':  0x22, '^':  0x23,
        '&':  0x24, '*':  0x25, '(':  0x26, ')':  0x27,

        # Row of numbers
        '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
        '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,

        # Navigation/Editing
        'INSERT': 0x49, 'HOME': 0x4A, 'PRIOR': 0x4B,
        'DELETE': 0x4C, 'END':  0x4D, 'NEXT':  0x4E,

        'ENTER': 0x28, 'ESCAPE': 0x29, 'BACKSPACE': 0x2A,
        'TAB':    0x2B, ' ':  0x2C,

        # Miscellaneous Symbols - grouped by key (one per row)
        '-': 0x2D, '_':  0x2D,
        '=': 0x2E, '+':  0x2E,
        '[': 0x2F, '{':  0x2F,
        ']': 0x30, '}':  0x30,
        '\\':0x31, "|":  0x31,
        ';': 0x33, ':':  0x33,
        "'": 0x34, '"':  0x34,
        '`': 0x35, '~':  0x35,
        ',': 0x36, '<':  0x36,
        '.': 0x37, '>':  0x37,
        '/': 0x38, '?':  0x38,

        #Arrow Keys
        'RIGHT': 0x4f, 'LEFT': 0x50, 'DOWN': 0x51, 'UP': 0x52,
        }

    # Some keys use the same hex code for example '1' and '!'. To get '!', SHIFT
    # modifier has to be used. This list contains these keys that need SHIFT.
    keys_with_shift = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_',
                       '+', '{', '}', '|', ':', '"', '~', '<', '>', '?']


    def __init__(self, config):
        super(GadgetKeyboard, self).__init__()
        self.emulator = config["pem_port"] # Initialize path to HID keyboard emulator
        self.filepath = "" # Initialize filepath for send_keystrokes_from_file()
        self.delay_between_keys = 0 # Delay (seconds) between keystrokes
        self.modifier = 0 # On default don't use modifier key
        self.line_number = 0 # Line number we are parsing from filepath
        logger.set_process_prefix()

    def send_keystrokes(self, filepath):
        '''
        Send keystrokes from a file to USB.

        Args:
            filepath: Path to the text file that contains keystrokes to send.

        The text file needs to have special syntax. Example:

            # These lines are comments
            # Set delay between keystrokes with 'DELAY' at the start of a line
            DELAY = 0.1
            # Send text by using ""
            "Hello world!"
            # Sending " is done by \"
            "\"Hello world!\""
            # Send special keys with < >
            <F2> <ENTER> <ESCAPE>
            # Use modifiers with < >, modifiers can have start and end
            <SHIFT_R> "hello world1" <SHIFT_R>
            # Spaces outside of "" and <> will be ignored
                   "This and the enter key will be sent to usb"    <ENTER>
            # Newlines are ignored

            # Everything else outside of "" and <> will raise an error
            this text will raise an error
            # Mix everything, but have a separate line for 'DELAY='
            DELAY=0.2
            <F2> "Hello world!" <ENTER> <SHIFT_L> "uppercase" <SHIFT_L>

        '''

        self.delay_between_keys = 0
        self.modifier = 0
        self.filepath = filepath

        with open(filepath, "r") as f:
            self.line_number = 1
            for line in f:
                line = line.strip()
                if line:
                    self.parse_line(line)
                self.line_number += 1

    def send_keystrokes_from_arg(self, lines):
        '''
        Send argument as keystrokes.

        Args:
            lines: String containing keystrokes to send. The string needs to have
                  special syntax which is explained in send_keystrokes_from_file
                  comments. If multiple lines are needed, \n can be used.

                  Example:

                    send_keystrokes("DELAY=0.1 \n \"Hello world\" \n <ENTER>")

        '''

        self.delay_between_keys = 0
        self.modifier = 0
        self.filepath = "arg"

        lines = lines.split("\n")
        self.line_number = 1
        for line in lines:
            self.parse_line(line)
            self.line_number += 1

    def parse_line(self, line):
        '''
        Parse a text file line.

        Args:
            line: Line from a text file.
        '''
        # If line starts with 'DELAY' set the delay
        if line[0:5] == "DELAY":
            try:
                self.delay_between_keys = float(line.split('=')[1].strip())
            except ValueError:
                raise LineSyntaxError(self.filepath, self.line_number,
                            "'" + line[6:].strip() + "' not a number")

        else:
            # Parse lines keys one at a time
            i = 0
            while i < len(line):
                key = line[i]

                # If key is "<" parse special key
                if key == "<":
                    i = self.parse_special(line, i)

                # If key is " start parsing text
                elif key == "\"":
                    i = self.parse_text(line, i)

                # If key is '#' ignore rest of the line
                elif key == "#":
                    return 0

                # If key is ' ', just ignore it
                elif key == " ":
                    pass

                # If key is anything else raise error
                else:
                    raise LineSyntaxError(self.filepath, self.line_number,
                                "Found '" + key + "' outside of <> and \"\"")

                i += 1

    def parse_special(self, line, i):
        '''
        Parse a special key that starts with '<' and ends with '>'.

        Args:
            line: Line from a text file that contains a special key.
            i: Iterator for the line that tells where the special key starts.

        Returns:
            i: Iterator for the line that tells where the special key ends.
        '''

        i += 1
        special = ""
        try:
            # Add letters to 'special' until '>' is found
            while line[i] != ">":
                special += line[i]
                i += 1
        except IndexError:
            raise LineSyntaxError(self.filepath, self.line_number,
                                "Didn't find closing '>'")

        # If the special key is a modifier, toggle it
        if special in self.modifier_codes:
            if self.modifier_codes[special] == self.modifier:
                self.modifier = 0
            else:
                self.modifier = self.modifier_codes[special]

        # If special key is a normal key, send it
        else:
            self.send_a_key(special)
            sleep(self.delay_between_keys)

        return i

    def parse_text(self, line, i):
        '''
        Parse text that starts and ends with ".

        Args:
            line: Line from a text file that contains "".
            i: Iterator for the line that tells where the starting " is.

        Returns:
            i: Iterator for the line that tells where the ending " is.
        '''
        i += 1
        try:
            # Send keys until " is found.
            while line[i] != "\"":
                key = line[i]
                # Allow sending ", by using '\'
                if key == "\\":
                    i += 1
                    key = line[i]

                self.send_a_key(key)
                sleep(self.delay_between_keys)
                i += 1

        except IndexError:
            raise LineSyntaxError(self.filepath, self.line_number,
                                "Didn't find closing \"")

        return i

    def send_a_key(self, key, timeout=20):
        '''
        HID keyboard message length is 8 bytes and format is:

            [modifier, reserved, Key1, Key2, Key3, Key4, Key6, Key7]

        So first byte is for modifier key and all bytes after third one are for
        normal keys. After sending a key stroke, empty message with zeroes has
        to be sent to stop the key being pressed. Messages are sent by writing
        to the emulated HID usb port in /dev/. US HID keyboard hex codes
        are used for translating keys.

        Args:
            key: A key to send, for example: "a", "z", "3", "F2", "ENTER"
            timeout: how long sending a key will be tried until quitting [s]
        '''
        usb_message = bytearray(self.empty.encode()) # Initialize usb message
        hex_key, _modifier = self.key_to_hex(key) # Translate key to hex code

        # Override self.modifier if the key needs a specific one
        if _modifier:
            modifier = _modifier
        else:
            modifier = self.modifier

        usb_message[2] = hex_key
        usb_message[0] = modifier

        time = 0
        while time < timeout:
            try:
                with open(self.emulator, "w") as emulator:
                    emulator.write(usb_message.decode()) # Send the key
                    emulator.write(self.empty) # Stop the key being pressed

            except IOError:
                logger.warning("Couldn't connect to host", "kb_emulator.log")
                time += 1
                sleep(1)

            else:
                logger.info("Sent key: " + key.ljust(5) + "  hex code: " +
                            format(hex_key, '#04x') + "  modifier: " +
                            format(modifier, '#04x'), "kb_emulator.log")
                return 0

        msg = "Keyboard emulator couldn't connect to host"
        logger.error(msg, "kb_emulator.log")
        raise TimeoutError(msg)

    def key_to_hex(self, key):
        """
        Returns the given keys (US) HID keyboard hex code and possible modifier
        key.

        Args:
            key: A key to translate for example: "a", "z", "3", "F2", "ENTER"
        """
        modifier_key = 0 # Initialize modifier_key as 0

        # Check if the key is in key_codes
        if key in list(self.key_codes.keys()):
            hex_key = self.key_codes[key]

            # Check if the key needs SHIFT modifier
            if key in self.keys_with_shift:
                modifier_key = self.modifier_codes["SHIFT_L"]

        # If the key isn't in key_codes, it should be a normal letter
        elif len(key) == 1:
            if 'A' <= key and key <= 'Z':
                hex_key = ord(key) - ord('A') + 0x04
                # Uppercase letters need SHIFT modifier
                modifier_key = self.modifier_codes["SHIFT_L"]

            elif 'a' <= key and key <= 'z':
                hex_key = ord(key) - ord('a') + 0x04

            else:
                raise TranslateError(self.filepath, self.line_number,
                                        "Couldn't translate key: '" + key +"'")

        else:
            raise TranslateError(self.filepath, self.line_number,
                                    "Couldn't translate key: <" + key +">")

        return hex_key, modifier_key


class TimeoutError(Exception):
    '''
    Error caused by not connecting to host device
    '''

class TranslateError(Exception):
    '''
    Error caused when key_to_hex() cant translate a key
    '''
    def __init__(self, _file, line, msg):
        super(TranslateError, self).__init__()
        self._file = _file
        self.line = line
        self.msg = msg

    def __str__(self):
        if self._file != "arg":
            return ("Error in file " + os.path.abspath(self._file) +
                " on line " + str(self.line) + ": " + self.msg)
        else:
            return ("Error in send_keystrokes() argument: "  + self.msg)

class LineSyntaxError(Exception):
    '''
    Error caused by text file syntax error
    '''
    def __init__(self, _file, line, msg):
        super(LineSyntaxError, self).__init__()
        self._file = _file
        self.line = line
        self.msg = msg

    def __str__(self):
        if self._file != "arg":
            return ("Error in file " + os.path.abspath(self._file) +
                " on line " + str(self.line) + ": " + self.msg)
        else:
            return ("Error in send_keystrokes() argument: "  + self.msg)
