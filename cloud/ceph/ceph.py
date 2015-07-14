#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2015, Alistair Israel <aisrael@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: ceph
short_description: Ceph module for Ansible.
description:
    - Use this module to run general Ceph commands.
version_added: "1.9"
options:
    cmd:
        required: true
        choices: [ "status", "quorum_status" ]
        description:
         - A ceph command to be executed. If C(cmd=status), executes C(ceph status) and returns the JSON formatted
           result in C(ceph_status). If C(cmd=quorum_status), executes C(ceph quorum_status) to show the monitor quorum,
           including which monitors are participating and which one is the leader, and returns the JSON result in C(quorum_status).
        required: true
    name:
        required: false
        default: "client.admin"
        description:
            - The client name for authentication
    cluster:
        required: false
        default: "ceph"
        description:
            - The cluster name
    conf:
        required: false
        default: ""
        description:
            - The Ceph configuration file to use
    connect_timeout:
        required: false
        default: 5
        description:
            - The timeout value for connecting to the cluster
requirements:
 - ceph
author: Alistair Israel
'''

EXAMPLES = '''
# Ceph status
- ceph: cmd=status
'''

import os

import datetime
import json

import rados

from ceph_argparse import \
    concise_sig, descsort, parse_json_funcsigs, \
    matchnum, validate_command, find_cmd_target, \
    send_command, json_command

CMDS = dict(
    status="status --format=json",
    quorum_status="quorum_status"
)

DICTS = dict(
    status={"prefix": "status", "format": "json"},
    quorum_status={"prefix": "quorum_status"}
)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            cmd =               dict(choices=["status", "quorum_status"], required=True),
            name =              dict(default="client.admin"),
            cluster =           dict(default="ceph"),
            conf =              dict(default=""),
            connect_timeout =   dict(type="int", default=5),
        ),
        supports_check_mode=False
    )

    cmd_param = module.params["cmd"]

    name = module.params["name"]
    clustername = module.params["cluster"]
    conffile = module.params["conf"]
    conf_defaults = {
        "log_to_stderr": "true",
        "err_to_stderr": "true",
        "log_flush_on_exit" : "true",
    }
    default_timeout = module.params['connect_timeout']

    startd = datetime.datetime.now()

    cluster_handle = rados.Rados(name=name, clustername=clustername,
                                 conf_defaults=conf_defaults,
                                 conffile=conffile)

    cluster_handle.connect(timeout=default_timeout)

    target = ("mon", "")
    valid_dict = DICTS[cmd_param]

    rc, outbuf, outs = json_command(cluster_handle, target=target, argdict=valid_dict)

    endd = datetime.datetime.now()

    if rc:
        module.fail_json(msg="Error: {0} {1}".format(rc, errno.errorcode[rc]))

    result = dict(
        cmd      = "ceph " + CMDS[cmd_param],
        rc       = rc,
        start    = str(startd),
        end      = str(endd),
        delta    = str(endd - startd),
        changed  = True
    )

    if cmd_param == "status":
        result["ceph_status"] = json.loads(outbuf)
    elif cmd_param == "quorum_status":
        result["quorum_status"] = json.loads(outbuf)
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
