#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import importlib
import json
import os
import signal
import time
import traceback
import subprocess

import pkg_resources
import psutil

from crontab import CronTab

from intelmq.lib import utils
from intelmq.lib.pipeline import PipelineFactory

from intelmq import (DEFAULTS_CONF_FILE, PIPELINE_CONF_FILE,
                     RUNTIME_CONF_FILE, VAR_RUN_PATH, BOTS_FILE)


APPNAME = "intelmqctl"

VERSION = pkg_resources.get_distribution("intelmq").version

DESCRIPTION = """
description: intelmqctl is the tool to control intelmq system.

Outputs are logged to /opt/intelmq/var/log/intelmqctl
"""

USAGE = """

    intelmqctl [start|stop|restart|status|debug] bot-id
    intelmqctl [start|stop|restart|status]
    intelmqctl list [bots|queues]
    intelmqctl log bot-id [number-of-lines [log-level]]
    intelmqctl clear queue-id
    intelmqctl check

    Starting a bot:
        intelmqctl start bot-id
    Stopping a bot:
        intelmqctl stop bot-id
    Restarting a bot:
        intelmqctl restart bot-id
    Get status of a bot:
        intelmqctl status bot-id

    Run a bot directly (blocking) for debugging purpose:
        intelmqctl debug bot-id

    Starting the botnet (all bots):
        intelmqctl start
        etc.

    Get a list of all configured bots:
        intelmqctl list bots

    Get a list of all queues:
        intelmqctl list queues

    Clear a queue:
        intelmqctl clear queue-id

    Get logs of a bot:
        intelmqctl log bot-id [number-of-lines [log-level]]
        Reads the last lines from bot log, or from system log if no bot ID was
        given. Log level should be one of DEBUG, INFO, ERROR or CRITICAL.
        Default is INFO. Number of lines defaults to 10, -1 gives all. Result
        can be longer due to our logging format!
"""

RETURN_TYPES = ['text', 'json', 'python']


class Parameters(object):
    pass


class BotManager:

    def __init__(self, config):
        self.config = config


    def bot_status(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('status', bot_id)
            print(output.decode('utf-8'))

        elif self.__get_run_mode(bot_id) == "scheduled":
            pass


    def bot_start(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('start', bot_id)

        elif self.__get_run_mode(bot_id) == "scheduled":
            self.__schedule_cronjob(bot_id)


    def bot_stop(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('stop', bot_id)

        elif self.__get_run_mode(bot_id) == "scheduled":
            self.__unschedule_cronjob(bot_id)


    def bot_restart(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('restart', bot_id)

        elif self.__get_run_mode(bot_id) == "scheduled":
            self.__unschedule_cronjob(bot_id)
            self.__schedule_cronjob(bot_id)


    def bot_enable(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('enable', bot_id)

        elif self.__get_run_mode(bot_id) == "scheduled":
            pass


    def bot_disable(self, bot_id):
        if self.__get_run_mode(bot_id) == "stream":
            output = self.__exec_systemd('disable', bot_id)

        elif self.__get_run_mode(bot_id) == "scheduled":
            pass


    def bot_activate_on_botnet(self):
        #self.__runtime_configuration[bot_id].set('botnet', True)
        raise ValueError('Option not implemented.')

    def bot_deactivate_on_botnet(self):
        #self.__runtime_configuration[bot_id].set('botnet', False)
        raise ValueError('Option not implemented.')

    def is_enable(self, bot_id):
        raise ValueError('Option not implemented.')

    def is_disable(self, bot_id):
        raise ValueError('Option not implemented.')

    def __get_instance(self, bot_id):
        return "%s@%s.service" % (self.__get_module(bot_id), bot_id)

    def __get_module(self, bot_id):
        return self.config[bot_id]['module']

    def __get_run_mode(self, bot_id):
        return self.config[bot_id]['run_mode']

    def __get_scheduled_time(self, bot_id):
        return self.config[bot_id]['scheduled_time']

    def __schedule_cronjob(self, bot_id):
        command = '/usr/local/bin/%s' % self.__get_module(bot_id)
        cron = CronTab(user='intelmq')
        job = cron.new(command=command, comment='IntelMQ Bot %s' % bot_id)
        job.setall(self.__get_scheduled_time(bot_id))
        job.enable()
        cron.write()

    def __unschedule_cronjob(self, bot_id):
        cron = CronTab(user='intelmq')
        cron.remove_all(comment='IntelMQ Bot %s' % bot_id)
        cron.write()

    def __exec_systemd(self, action, bot_id):
        instance = self.__get_instance(bot_id)
        return subprocess.check_output(["systemctl", action, instance])


class IntelMQController():

    def __init__(self, interactive=False, quiet=False):

        self.mode_return_type = 'python' # [text, json, python]

        # TODO: run systemctl command with --user intelmq
        if os.geteuid() == 0:
            print('\nRunning intelmq as root is highly discouraged!\n')

        # NOTE: stolen functions from the bot file
        # IMPORTANT: this will not work with various instances of REDIS
        self.pipeline_configuration = self.load_configuration(PIPELINE_CONF_FILE)
        self.runtime_configuration = self.load_configuration(RUNTIME_CONF_FILE)
        self.defaults_configuration = self.load_configuration(DEFAULTS_CONF_FILE)

        if interactive:
            self.console, self.arguments = self.__read_arguments()

        self.manager = BotManager(
            self.runtime_configuration
        )


    def run(self):
        results = None

        if self.arguments.action in ['start', 'restart', 'stop', 'status']:

            # Execute bot action                    
            if self.arguments.parameter:
                call_method = getattr(self, "bot_" + self.arguments.action)
                results = call_method(self.arguments.parameter[0])

            # Execute botnet action
            else:
                call_method = getattr(self, "botnet_" + self.arguments.action)
                results = call_method()


        elif self.arguments.action == ['debug','enable', 'disable']:

            # Execute bot action
            if self.arguments.parameter and len(self.arguments.parameter) == 1:
                call_method = getattr(self, "bot_" + self.arguments.action)
                results = call_method(self.arguments.parameter[0])
            # Bad argument, print help
            else:
                self.print_help_bad_argument("Exactly one bot-id must be given for run.")


        elif self.arguments.action == 'list':

            # Execute list action
            if self.arguments.parameter or self.arguments.parameter[0] in ['bots', 'queues']:
                method_name = "list_" + self.arguments.parameter[0]
                call_method = getattr(self, method_name)
                results = call_method()

            # Bad argument, print help    
            else:
                self.print_help_bad_argument("Second argument for list must be 'bots' or 'queues'.")


        elif self.arguments.action == 'log':

            # Execute log action
            if self.arguments.parameter:
                results = self.read_log(*self.arguments.parameter)

            # Bag argument, print help
            else:
                self.print_help_bad_argument("You must give parameters for 'log'.")
            

        elif self.arguments.action == 'clear':

            # Execute clear action
            if self.arguments.parameter:
                results = self.clear_queue(self.arguments.parameter[0])

            # Bag argument, print help
            else:
                self.print_help_bad_argument("Queue name not given.")
            

        elif self.arguments.action == 'check':

            # Execute check action
            results = self.check()


    def bot_status(self, bot_id):
        return self.manager.bot_status(bot_id)


    def bot_start(self, bot_id):
        return self.manager.bot_start(bot_id)


    def bot_stop(self, bot_id):
        return self.manager.bot_stop(bot_id)


    def bot_enable(self, bot_id):
        return self.manager.bot_enable(bot_id)


    def bot_disable(self, bot_id):
        return self.manager.bot_disable(bot_id)


    def bot_restart(self, bot_id):
        status_stop = self.bot_stop(bot_id)
        status_start = self.bot_start(bot_id)
        return (status_stop, status_start)


    def botnet_status(self):
        botnet_status = {}
        for bot_id in sorted(self.runtime_configuration.keys()):
            botnet_status[bot_id] = self.bot_status(bot_id)
        return botnet_status


    def botnet_start(self):
        botnet_status = {}
        for bot_id in sorted(self.runtime_configuration.keys()):
            if self.runtime_configuration[bot_id].get('botnet', True):
                botnet_status[bot_id] = self.bot_start(bot_id)

        return botnet_status


    def botnet_stop(self):
        botnet_status = {}
        for bot_id in sorted(self.runtime_configuration.keys()):
            botnet_status[bot_id] = self.bot_stop(bot_id)
        return botnet_status


    def botnet_reload(self):
        botnet_status = {}
        for bot_id in sorted(self.runtime_configuration.keys()):
            botnet_status[bot_id] = self.bot_reload(bot_id)
        return botnet_status


    def botnet_restart(self):
        self.botnet_stop()
        return self.botnet_start()


    def bot_debug(self, bot_id):
        try:
            bot_module = self.runtime_configuration[bot_id]['module']
        except KeyError:
            log_bot_error('notfound', bot_id)
            return 'error'

        module = importlib.import_module(bot_module)
        bot = getattr(module, 'BOT')
        instance = bot(bot_id)
        instance.start()


    def list_bots(self):
        pass

    def list_queues(self):
        pass

    def clear_queue(self, queue):
        pass

    def read_log(self, bot_id, number_of_lines=10, log_level='INFO'):
        pass

    def read_bot_log(self, bot_id, log_level, number_of_lines):
        pass

    def check(self):
        pass

    def load_configuration(self, configuration):
        try:
            configuration_object = utils.load_configuration(configuration)
        except ValueError as exc:
            exit('Invalid syntax in %r: %s' % (configuration, exc))
        return configuration_object

    # MOVEME: to log section
    def print_help_bad_argument(message):
        print(message)
        self.console.print_help()
        exit(2)

    def __read_arguments(self):
        console = argparse.ArgumentParser(
            prog=APPNAME,
            usage=USAGE,
            epilog=DESCRIPTION
        )

        console.add_argument('-v', '--version',
                            action='version', version=VERSION)

        console.add_argument('--type', '-t', choices=RETURN_TYPES,
                            default=RETURN_TYPES[0],
                            help='choose if it should return regular text '
                                 'or other machine-readable')

        console.add_argument('action',
                            choices=['start', 'stop', 'restart', 'status',
                                     'reload', 'debug', 'list', 'clear',
                                     'help', 'log', 'check'],
                            metavar='[start|stop|restart|status|reload|debug'
                                    '|list|clear|log|check]')
        console.add_argument('parameter', nargs='*')

        console.add_argument('--quiet', '-q', action='store_const',
                            help='Quiet mode, useful for reloads initiated'
                                 'scripts like logrotate',
                            const=True)

        arguments = console.parse_args()

        if arguments.action == 'help':
            console.print_help()
            exit(0)

        return console, arguments


def main():
    intelmqctl = IntelMQController(interactive=True)
    intelmqctl.run()


if __name__ == "__main__":
    main()
