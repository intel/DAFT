# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
# Author Erkka Kääriä <erkka.kaaria@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
"""
Parser for a minimal subset of ansi control codes.

Used to parse the files created by serial recorder
"""


# Note: Galileo in general seems to love to absolutely mangle the control codes
# to the point where even bash has trouble parsing them correctly. The approach
# here is that any codes that make no sense are just ignored. This may cause the
# output to occasionally be slightly corrupted, but as long as it is even
# somewhat readable, it is good enough

from __future__ import print_function
import os

class Token(object):
    """Class that stores the constants for code tokens"""
    CLEAR_SCREEN = 1
    MOVE_CURSOR = 2
    RESET_COLOR = 3


def parse_file(input_file_name):
    """Parses the file with given name. Original file is backed up.

    Args:
        input_file_name: Name of the input file
    Returns:
        None

    Note: Backup will be named as raw_original_name
          Example; foo.log will be backed up as raw_foo.log

    Note: The working file for parser is temp_original_file. This one will be
          renamed to original_file after the original file has been backed up

    """
    raw_input_file_name = "raw_" + input_file_name
    temp_name = "temp_" + input_file_name

    with open(input_file_name, "rb") as input_file:
        with open(temp_name, "w") as output_file:
            do_parse(input_file, output_file)


    # back up the file, just in case
    print("Backing up " + input_file_name + " as " + raw_input_file_name + ".")
    os.rename(input_file_name, raw_input_file_name)

    # And rename the temp output file
    os.rename(temp_name, input_file_name)


def do_parse(input_file, output_file):
    """
    Parses the given input_file and stores the result in output_file

    Args:
        input_file: Input file. Will not be modified
        output_file: Output file. Parsed text will be written into this
    Returns:
        None

    Note: input_file and output_file must not be the same file
    """
    # width\height arbitrarily set to be large enough so it works
    # (no out of bounds array accesses)
    width = 300
    height = 32

    # current row\column position; defines where next characters will be written
    row = 0
    column = 0

    # avoids printing extra empty lines
    last_row_with_characters = 0

    screen_buffer = create_screen_buffer(height, width)

    escape_char_code = 27


    # use for heuristic write & clear screen
    control_codes_after_top_left_move = False

    while True:
        char = input_file.read(1)
        if not char:
            break
        elif char == '\n':
            row += 1
            last_row_with_characters += max(last_row_with_characters, row)
            column = 0
        elif ord(char) == escape_char_code:
            ret = parse_token(input_file)
            if ret != None:
                if ret[0] == Token.CLEAR_SCREEN:
                    control_codes_after_top_left_move = True
                    write_and_clear_buffer(
                        output_file,
                        screen_buffer,
                        min(height, last_row_with_characters+1),
                        width)

                    column = 0
                    row = 0
                    last_row_with_characters = 0
                elif ret[0] == Token.MOVE_CURSOR:

                    if ret[1] == 0 and ret[2] == 0:
                        control_codes_after_top_left_move = False
                    else:
                        control_codes_after_top_left_move = True

                    # we just ignore the move token if it is out of
                    # bounds
                    if ret[1] < height and ret[2] < width:
                        row = ret[1]
                        column = ret[2]
                        last_row_with_characters += max(
                            last_row_with_characters,
                            row)
                elif ret[0] == Token.RESET_COLOR:
                    # We enter the world of messy heuristic here. Sometimes
                    # parser ended up writing bios screens and whatnot on top
                    # of real, relevant log messages. These scenarios were
                    # typically preceded by MOVE<1, 1>, followed by
                    # log messages, followed by reset color code. So we use
                    # this as heuristic to print & clear screen, just in case

                    if not control_codes_after_top_left_move:
                        control_codes_after_top_left_move = True
                        write_and_clear_buffer(
                        output_file,
                        screen_buffer,
                        min(height, last_row_with_characters+1),
                        width)

        else:
            screen_buffer[row][column] = char
            column += 1


        if column == width:
            column = 0
            row += 1
            last_row_with_characters = max(row, last_row_with_characters)

        if row == height:
            write_and_clear_buffer(
                output_file,
                screen_buffer,
                height,
                width)

            row = 0
            last_row_with_characters = 0

    # write any remaining characters in the buffer
    write_and_clear_buffer(
        output_file,
        screen_buffer,
        min(height, last_row_with_characters+1),
        width)


def create_screen_buffer(height, width):
    """Initialize and return screen buffer"""
    return [['\0' for _ in range(width)] for _ in range(height)]


def parse_token(input_file):
    """
    Parse ansi control token

    Args:
        file: file handle for the file we are parsing
    Returns:
        None, if no valid or supported ansi control token was found
        Array containing code specific data, if code was found
    """
    # note - we really would like to use peek() here, but python standard
    # file api does not provide such function
    char = input_file.read(1)

    # not ANSI control code
    if char != '[':
        # as we read a character, move file position back by one character
        input_file.seek(-1, 1)
        return None

    code = ""

    # keep reading until we find upper or lower case ascii letter or [
    while True:
        char = input_file.read(1)
        # unexpected EOF - return none
        if not char:
            return None

        # there are some corrupted\invalid commands in the output;
        # we assume any command that ends in '[' is actually cursor move.
        # assumption is based on manual inspection of corrupted codes
        if char.isalpha() or char == '[':
            # clear screen
            if char == 'J':
                return parse_clear_screen(code)
            # color code
            # we ignore this, with the exception <ESC>[0m which is color reset
            # code. Reset color code is to clear screen under certain
            # circumstances
            elif char == 'm':
                if code == "0":
                    return [Token.RESET_COLOR]

                return None
            # move cursor to <Row, Column>
            elif char == 'H' or char == 'f' or char == '[':
                return parse_cursor_move(code)
            # hide\show cursor - ignore
            elif char == 'h':
                return None
            else:
                # unimplemented command
                return None
        else:
            code += char


def parse_clear_screen(code):
    """
    Parse clear screen control code <ESC>[nJ

    Args:
        code: String containing characters between '<ESC>[' and 'J'
              example; <ESC>[2J -> code is 2
    Returns:
        None on invalid or unsupported code
        Array containing the type of clear screen command, depending on code
            argument
    """

    # clear from cursor to the end of screen
    # not implemented
    if code == "" or code == "0":
        return None
    # clear from cursor to the beginning of screen
    # not implemented
    elif code == "1":
        return None
    elif code == "2":
        return [Token.CLEAR_SCREEN]
    # bad command - ignore
    else:
        return None

def parse_cursor_move(code):
    """
    Parse cursor move control code <ESC>[n;mH or <ESC>[n;mf

    Args:
        code: String containing characters between '<ESC>[' and 'H' or 'f'
              example; <ESC>[4;2H -> code is 4;2
    Returns:
        Array containing [Token.MOVE_CURSOR, row, column]
            all values are integers
    """
    split_code = str(code).split(";")

    if len(split_code) < 2:
        return None

    row = split_code[0]
    column = split_code[1]

    # filter any non-numeric characters
    filter_function = lambda x: x.isdigit()
    row = list(filter(filter_function, row))
    column = list(filter(filter_function, column))

    if row == "":
        row = "1"
    if column == "":
        column = "1"

    # row\column use one based indexing, but screen buffer
    # uses zero based indexing.
    row = int(row[0]) - 1
    column = int(column[0]) - 1
    return [Token.MOVE_CURSOR, row, column]



# prints and clears buffer
# we use null terminator characters to signify where the buffer ends
# (that is, empty buffer is filled with null terminators)
# this prevents printing any extra whitespace characters, as the buffer
# width is arbitrary and does not match actual screen dimensions
def write_and_clear_buffer(output_file, screen_buffer, last_row, width):
    """
    Prints and clears screen buffer

    Args:
        output_file: The file where the output is written
        screen_buffer: The screen buffer
        last_row: Last row with characters; remaining rows will be skipped
        width: Maximum row width
    Returns:
        None
    """
    for row in range(last_row):
        line = ""
        line_width = get_line_length(row, screen_buffer, width)
        for column in range(line_width):
            char = screen_buffer[row][column]
            screen_buffer[row][column] = '\0'
            # replace null with space
            if char == '\0':
                char = ' '
            # skip newline symbols to make output prettier
            if char == '\n':
                continue

            line += char.decode("utf-8")

        print(line, file=output_file)

# Return line length by returning the position of null byte after first
# non-null character, when scanning from right
#
# Example: "hello\0" returns 5
#          "hello\0world\0" returns 11
#          "hello\0world\0\0\0\0\0\0" returns 11
#
def get_line_length(row, screen_buffer, width):
    """
    Return line length

    Args:
        row: Current row
        screen_buffer: The screen buffer
        width: Maximum row width
    Returns:
        Line length: Line length, up to width
    """
    for column in reversed(list(range(width))):
        if screen_buffer[row][column] != '\0':
            return column + 1
    return 0
