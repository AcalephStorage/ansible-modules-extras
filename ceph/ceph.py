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
version_added: "1.8"
options:
  cmd:
    required: true
    choices: [ "status", "quorum_status" ]
    description:
     - A ceph command to be executed. If C(cmd=status), executes C(ceph status) and returns the JSON formatted
       result in C(ceph_status). If C(cmd=quorum_status), executes C(ceph quorum_status) to show the monitor quorum,
       including which monitors are participating and which one is the leader, and returns the JSON result in C(quorum_status).
    required: true
requirements:
 - ceph
author: Alistair Israel
'''

EXAMPLES = '''
# Ceph status
- ceph: status
'''

import os

import datetime
import json

CMDS = dict(
    status='status --format=json',
    quorum_status='quorum_status'
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            cmd=dict(choices=['status', 'quorum_status'], required=True)
        ),
        supports_check_mode=False
    )

    cmd_param = module.params['cmd']
    cmd = 'ceph ' + CMDS[cmd_param]
    startd = datetime.datetime.now()
    rc, out, err = module.run_command(cmd)
    endd = datetime.datetime.now()
    delta = endd - startd

    result = dict(
        cmd      = cmd,
        stderr   = err.rstrip("\r\n"),
        rc       = rc,
        start    = str(startd),
        end      = str(endd),
        delta    = str(delta),
        changed  = True
    )

    if cmd_param == 'status':
        result['ceph_status'] = json.loads(out.rstrip("\r\n"))
    elif cmd_param == 'quorum_status':
        result['quorum_status'] = json.loads(out.rstrip("\r\n"))

    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
