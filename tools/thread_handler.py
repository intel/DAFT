# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
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

'''
Class for handling threads.
'''

class Thread_handler(object):
    '''
    Flags: Dictionary with aĺl flags added with set_flag()
    Threads: List with all thread objects
    '''
    RECORDERS_STOP = "recorders_stop"

    FLAGS = {}
    THREADS = []

    @staticmethod
    def add_thread(thread):
        '''
        Add thread object to THREADS list
        '''
        Thread_handler.THREADS.append(thread)

    @staticmethod
    def get_threads():
        '''
        Return THREADS list
        '''
        return Thread_handler.THREADS

    @staticmethod
    def set_flag(flag):
        '''
        Add/change flag in FLAGS dictionary
        '''
        Thread_handler.FLAGS[flag] = True

    @staticmethod
    def unset_flag(flag):
        '''
        Add/change flag in FLAGS dictionary
        '''
        Thread_handler.FLAGS[flag] = False

    @staticmethod
    def get_flag(flag):
        '''
        Return flags value from FLAGS dictionary, if one isn't found return 0
        '''
        try:
            return Thread_handler.FLAGS[flag]
        except KeyError:
            return None
