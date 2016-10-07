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
Functions for logging. This module was created so when 'aft --checkall' is used
every machine gets its own [machine]_aft.log and [machine]_ssh.log instead
of every machines logging to aft.log and ssh.log. When 'aft --checkall accurate'
is used, logging messages will be written to same aft.log and ssh.log files.

If new logger is needed, Logger.info()/.debug()/.warning()... makes new
one automatically when called with 'filename=' argument. Loggers are made
process specific. Using set_process_prefix() function, prefix to processes
filenames can be added/changed.
'''

import os
import logging
import aft.config as config

class Logger(object):
    '''
    Logger class for holding logging methods and variables

    PROCESSES: Dictionary with processes filename prefixes
    LOGGING_LEVEL: Logging level threshold for new loggers
    '''

    PROCESSES = {}
    LOGGING_LEVEL = logging.INFO

    @staticmethod
    def level(logging_level):
        '''
        Change new loggers logging threshold level

        Args:
            logging_level (logging.INFO, logging.DEBUG, logging.WARNING etc.)
        '''
        Logger.LOGGING_LEVEL = logging_level

    @staticmethod
    def set_root_logger_settings():
        '''
        Initialize root logger settings. At the time of writing, only PEM is
        using root logger (logging.info(), logging.warning() etc.)
        '''
        logging.basicConfig(filename="pem_" + config.AFT_LOG_NAME,
                            level=Logger.LOGGING_LEVEL,
                            filemode="w",
                            format='%(asctime)s - %(levelname)s - %(message)s')

    @staticmethod
    def set_process_prefix(log_prefix=""):
        '''
        Add/change process's filename prefix to dictionary

        Args:
            log_prefix: String for filename prefix
        '''
        Logger.PROCESSES[str(os.getpid())] = log_prefix

    @staticmethod
    def get_logger(filename):
        '''
        Gets logger. If there isn't any handlers for it, it sets up a new logger

        Args:
            filename: String for filename/logger suffix, default is aft.log
        '''
        logger = logging.getLogger(str(os.getpid()) + filename)
        if not logger.handlers:
            Logger._make(filename)

        return logger

    '''
    Methods for logging to log files. On default methods log to aft.log file.

    Args:
        log_message: String to log
        filename: String for filename/logger suffix, default is aft.log
    '''
    @staticmethod
    def info(log_message, filename="aft.log"):
        Logger.get_logger(filename).info(log_message)

    @staticmethod
    def debug(log_message, filename="aft.log"):
        Logger.get_logger(filename).debug(log_message)

    @staticmethod
    def warning(log_message, filename="aft.log"):
        Logger.get_logger(filename).warning(log_message)

    @staticmethod
    def critical(log_message, filename="aft.log"):
        Logger.get_logger(filename).critical(log_message)

    @staticmethod
    def error(log_message, filename="aft.log"):
        Logger.get_logger(filename).error(log_message)


    @staticmethod
    def _make(filename, file_mode="w"):
        '''
        Makes new logger. Logs name will be [prefix]+[filename]. Prefix will be
        taken from PROCESSES dictionary. Adding PROCESS'S prefix to dictionary
        is done with set_process_prefix(log_prefix='').

        Args:
            filename: String for filename suffix
            file_mode: Logger handlers file mode, default 'w' = write
        '''

        logger = logging.getLogger(str(os.getpid()) + filename)
        logger.setLevel(Logger.LOGGING_LEVEL)

        # If set_process_prefix() hasn't been used before making new logger,
        # prefix will be process's name so every process's' log filename will be
        # different
        if not str(os.getpid()) in Logger.PROCESSES:
            Logger.PROCESSES[str(os.getpid())] = str(os.getpid())
            print("Process's logger hasn't been initialized with set_process_prefix.")

        filename = Logger.PROCESSES[str(os.getpid())] + filename
        handler = logging.FileHandler(filename, mode=file_mode)
        handler.setLevel(Logger.LOGGING_LEVEL)
        _format = ('%(asctime)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter(_format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False #Don't pass anything to parent logger (root)
