Table of Contents
=================

   * [Concepts](#concepts)
      * [Run mode](#run-mode)
      * [Process management](#process-management)
      * [Run Modes with Process Management](#run-modes-with-process-management)
      * [Onboot](#onboot)
   * [intelmqctl](#intelmqctl)
      * [Overview](#overview)
         * [Principles](#principles)
         * [Syntax](#syntax)
         * [Generic flags](#generic-flags)
      * [intelmqctl start action](#intelmqctl-start-action)
      * [intelmqctl stop action](#intelmqctl-stop-action)
      * [intelmqctl restart action](#intelmqctl-restart-action)
      * [intelmqctl reload action](#intelmqctl-reload-action)
      * [intelmqctl configtest action](#intelmqctl-configtest-action)
      * [intelmqctl status action](#intelmqctl-status-action)
      * [intelmqctl enable action](#intelmqctl-enable-action)
      * [intelmqctl disable action](#intelmqctl-disable-action)


# Concepts


## Run mode

Each bot has two modes of execution, as follows:

* **continuous:** bot will run and process messages indefinitely.
* **scheduled:** bot will start at the defined `schedule_time`, and after on successfully execution will exit.

The following snippet exemplifies the bot's run modes configuration.
 
**on runtime configuration:**
```
    "abusech-domain-parser": {
        ...
        "parameters": {
            "run_mode": "< continuous / scheduled >"
        }
    }
```

**Schedule time parameter clarification:**
`schedule_time` is a parameter defined per each bot on runtime configuration which specifies the scheduled time when the bot should run. This parameter needs to be defined using crontab syntax. Attention that this parameter is only applicable to bots configured as `scheduled` run_mode.


## Process management

IntelMQ process management has two approaches, one based on Systemd and the other on PID.
The default choice is the Systemd that will manage the IntelMQ processes. Changing the configuration back to PID, will make IntelMQ work as previously.

**on defaults configuration:**
```
{
    ...
    "process_manager": "< pid / systemd >"
    ...
}
```

### Systemd

**Systemd Services:** To support the Systemd approach; this proposal provides template files for three types of systemd services.

1. `<bot-module>.continuous.service`: this template should be instantiated by intelmqctl per bot module configured with `run_mode: continuous`.
2. `<bot-module>.scheduled.service`: this template should be instantiated by crontab per bot module configured with `run_mode: scheduled`.
3. `intelmq.scheduled_bots_onboot.service`: this template file exists to manage bots configured with `run_mode: scheduled`, which need to be configured on crontab during operating system boot. Please note, that this service MUST be executed only onboot and before crontab service starts.


## Run Modes with Process Management

![architecture](https://s2.postimg.org/6hmikcg4p/intelmq_bots_management_1.png)


## Onboot

An IntelMQ bot configured with onboot enabled will start automatically when operating system starts. This parameter is also commonly called "autostart".

```
    "abusech-domain-parser": {
        ...
        "parameters": {
            "onboot": true
        }
    }
```

**Note:** this configuration parameter only works with `Systemd` as Process Manager. If you are using `PID`, you need to create your own init scripts.

# intelmqctl

## Overview

### Principles

There are principles defined for `intelmqctl` in order to simplify this document and remove duplication of phrases and special notes for some cases, therefore `intelmqctl` will always:
* execute the bot background, not in foreground.
* provide the possibility to be executed in interaction mode or in non-interaction mode using flags.
* provide the best log message in order to give additional information to sysadmin about the actions performed. 
* check if there is any issue with configurations (runtime, defaults, pipeline) regarding all bots even if just one action to one bot has been executed.
 * in case a bot is running but some configuration for that bot is missing in one of the files, the action will not be performed and sysadmin will receive a warning message
 * intelmqctl will automatically re-add the missing configuration and ask to syadmin to re-run the command again, now with the configurations cleaned.


### Syntax
```
intelmqctl <action command> <bot_id> <flags>
```

### Generic flags

* `--filter`: this flag will provide to sysadmin a quick way to specify which bots this action will be apply. The filtering can be done using the configuration keys parameters as the following examples:

```
intelmqctl start --filter "run_mode:scheduled, group:Collectors"
```
```
intelmqctl stop --filter "run_mode:continuous, group:Outputs"
```

## intelmqctl start action

### Command

```
intelmqctl start <bot_id> <flags>
```

### Description

The start command will start normally a bot configured as continuous run mode and for a bot configured as scheduled run mode it will put an entry on crontab ready to be trigger by Crontab on scheduled time defined on bot configuration. This means that start command for scheduled bots could be called `intelmqctl schedule` and the opposite `intelmqctl unschedule`, however, having one command for all run modes types can be simplified with the following principle:
* intelmqctl start will start (now or scheduling) a bot accordingly to the bot configuration (continuous or scheduled run mode) without the user needs to use different commands.


### Procedure

**> 1. Bot status check:**
* if bot is running or is scheduled on crontab, intelmqctl will not perform any action

**> 2.1 Bot configured with "Continuous" Run Mode and "PID" Process Manager:**
* execute start action on bot and write PID file

**> 2.2 Bot configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* execute `systemctl start <bot-module>.continuous@<bot_id>.service`

**> 2.3 Bot configured with "Scheduled" Run Mode and "PID" Process Manager:**
* add configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`

**> 2.4 Bot configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* add configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`

#### Specific flags

* `--oneshot`: this flag will execute the bot now and process successfully one message and then exit. This action MUST NOT taking into account `run_mode`.


* `--foreground`: this flag will execute the bot in foreground, showing the logs in the terminal window.


* `--cron-exec`: this flag will execute the bot now and process successfully one message and then exit. This action **MUST only be used** to configure a scheduled bot on Crontab configuration and in a normal case an user don't need to be aware of it. Performing `intelmqctl start <bot-id>` where `bot-id` is a bot configured as scheduled will automatically put a new entry on Crontab with this flag `--cron-exec`. In practice, the command which will be used in case Process Manager is systemd, will be `systemctl start <bot-module>.scheduled@<bot_id>.service`


## intelmqctl stop action

### Command

```
intelmqct stop <bot_id> <flags>
```

### Description

The stop command will stop normally a bot configured as continuous run mode and for a bot configured as scheduled run mode it will remove the entry from crontab.


### Procedure

**> 1. Bot status check:**
* if bot is stopped, intelmqctl will not perform any action.

**> 2.1 Bot configured with "Continuous" Run Mode and "PID" Process Manager:**
* execute stop action on bot and remove PID file

**> 2.2 Bot configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* execute `systemctl stop <bot-module>.continuous@<bot_id>.service`

**> 2.3 Bot configured with "Scheduled" Run Mode and "PID" Process Manager:**
* remove configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`

**> 2.4 Bot configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* remove configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`


## intelmqctl restart action

### Command

```
intelmqctl restart <bot_id> <flags>
```

### Description

The restart command will call the stop and start commands.


### Procedure

**> 1. Independently of bot status and run mode and process manager configurations:**
* `intelmqctl` will use the stop action command and start action command to perform the restart, therefore, there is no additional information required here, is only to actions commands being executed already explained.



## intelmqctl reload action

### Command

```
intelmqctl reload <bot_id> <flags>
```

### Description

The reload command will tell to the bot (if bot is running) to reload the configuration in order to execute accordingly to the new configuration.


### Procedure

**> 1.1 Bot configuration (extra) checks:**
* Check if bot has a new `run_mode` value and is running/scheduled, intelmqctl will proceed following intelmqctl principles.

**> 1.2 Bot status check:**
* if bot is stopped, intelmqctl will not perform any action.

**> 2.1 Bot is running and configured with "Continuous" Run Mode and "PID" Process Manager:**
* execute reload action on bot

**> 2.2 Bot is running and configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* execute `systemctl reload <bot-module>.continuous@<bot_id>.service`

**> 2.3 Bot is running and configured with "Scheduled" Run Mode and "PID" Process Manager:**
* check and rewrite (if needed) the configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`

**> 2.4 Bot is running and configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* check and rewrite (if needed) the configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`


## intelmqctl configtest action

### Command
```
intelmqctl configtest <bot_id> <flags>
```

### Description

The configtest command will perform multiple tests on configuration in order to provide help to the sysadmin during bots configuration.


### Procedure

**> 1.1 Check configuration format:**
* in case the configuration format (JSON) has problems, give an error message to user about the config format

**> 1.2 Check bots configuration parameters:**
* in case some bot configuration parameters has problems, give an error message to user about the bot config parameter.


## intelmqctl status action

### Command
```
intelmqctl status <bot_id> <flags>
```

### Description

The status command will provide information about the status of bot(s).


### Procedure

**> 1.1 Bot configured with "Continuous" Run Mode and "PID" Process Manager:**
* check PID file exists

**> 1.2 Bot configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* execute `systemctl status <bot-module>.continuous@<bot_id>.service`

**> 1.3 Bot configured with "Scheduled" Run Mode and "PID" Process Manager:**
* check configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`

**> 1.4 Bot configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* check configuration line on crontab such as `<schedule_time> intelmqctl start <bot_id> --cron-exec # <bot_id>`



#### Examples

**Example 1 (Ouput Proposal)**

| bot_id    | run_mode    | scheduled_time (if applicable) | status             | onboot          | configtest   |
|-----------|-------------|--------------------------------|--------------------|-----------------|--------------|
| my-bot-1  | scheduled   | -                              | scheduled          | yes             | valid        |

Also intelmqctl may print the last 10 log lines from the log of this bot.

**Example 2 (Ouput Proposal)**

| bot_id    | run_mode    | scheduled_time (if applicable) | status             | onboot | configtest   |
|-----------|-------------|--------------------------------|--------------------|--------|--------------|
| my-bot-2  | continuous  | 1 * * * *                      | running            | no     | invalid      |

Also intelmqctl may print the last 10 log lines from the log of this bot.


## intelmqctl enable action

### Command
```
intelmqctl enable <bot_id> <flags>
```

### Description

The enable command will define the bot to start automatically when operating system starts.


### Procedure

**> 1.1 Bot configured with "Continuous" Run Mode and "PID" Process Manager:**
* intelmqctl will not perform any action and log a message explaining why (for more details see "Onboot" sub-section under "Concepts" section)

**> 1.2 Bot configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* intelmqctl will change `onboot` configuration parameter to `true` value.
* execute `systemctl enable <bot-module>.continuous@<bot_id>.service`

**> 1.3 Bot configured with "Scheduled" Run Mode and "PID" Process Manager:**
* intelmqctl will not perform any action and log a message explaining why (for more details see "Onboot" sub-section under "Concepts" section)

**> 1.4 Bot configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* intelmqctl will change `onboot` configuration parameter to `true` value.
* `intelmq.scheduled_bots_onboot.service` will be responsible to configure crontab onboot, therefore, this bot will be configured on crontab during the boot.


## intelmqctl disable action

### Command
```
intelmqctl disable <bot_id> <flags>
```

### Description

The disable command will define the bot to NOT start automatically when operating system starts.


### Procedure

**> 1.1 Bot configured with "Continuous" Run Mode and "PID" Process Manager:**
* intelmqctl will not perform any action and log a message explaining why (for more details see "Onboot" sub-section under "Concepts" section)

**> 1.2 Bot configured with "Continuous" Run Mode and "Systemd" Process Manager:**
* intelmqctl will change `onboot` configuration parameter to `false` value.
* execute `systemctl disable <bot-module>.continuous@<bot_id>.service`

**> 1.3 Bot configured with "Scheduled" Run Mode and "PID" Process Manager:**
* intelmqctl will not perform any action and log a message explaining why (for more details see "Onboot" sub-section under "Concepts" section)

**> 1.4 Bot configured with "Scheduled" Run Mode and "Systemd" Process Manager:**
* intelmqctl will change `onboot` configuration parameter to `false` value.
* `intelmq.scheduled_bots_onboot.service` will be responsible to configure crontab onboot, therefore, this bot will NOT be configured on crontab during the boot.
