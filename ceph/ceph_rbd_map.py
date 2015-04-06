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
module: ceph_rbd_map
short_description: Ceph rbd map module for Ansible.
description:
 - Use this module to manage Ceph rbd mappings.
version_added: "1.8"
options:
    name:
        required: true
        description:
            - The rbd or image name.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Whether the rbd mapping should be present or not on the remote host.
    image:
        required: false
        description:
            - Required for C(state=present). The image name to use for the rbd.
    pool:
        required: false
        description:
            - The pool name to use for the rbd operations.
    id:
        required: false
        description:
            - Specifies the username (without the C(client.) prefix) to use with the map command.
    options:
        required: false
        description:
            - Specifies which options to use when mapping an image. C(options) is a comma-separated
              string of options (similar to C(mount(8)) mount options).
    read_only:
        required: false
        choices: [ "yes", "no" ]
        description:
            - Map the image read-only.  Equivalent to C(-o ro).
requirements:
 - ceph
author: Alistair Israel
'''

EXAMPLES = '''
# Map an image named "rbd1"
- ceph_rbd_map: state=present name=rbd1
'''

import os
import datetime
import json

import rados
import rbd

def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(choices=['present', 'absent'], default='present'),
            name=dict(required=True),
            pool=dict(),
            id=dict(),
            options=dict(),
            read_only=dict(type='bool')
        ),
        supports_check_mode=False
    )

    # Figure out the existing mappings
    def list_mappings():
        rc, out, err = module.run_command("rbd showmapped --format json")
        ceph_rbd_mapping = json.loads(out.rstrip("\r\n"))
        return { v['name']: { kk: vv for kk, vv in v.items() if not kk == 'name' } for k, v in ceph_rbd_mapping.items()}

    name = module.params['name']
    state = module.params['state']
    pool = module.params['pool']
    id_param = module.params['id']

    result = {}
    result['name'] = name

    def sh(cmd):
        startd = datetime.datetime.now()
        rc, out, err = module.run_command(cmd)
        endd = datetime.datetime.now()
        delta = endd - startd
        result['rc'] = rc
        result['cmd'] = cmd
        result['stdout'] = out.rstrip("\r\n")
        result['stderr'] = out.rstrip("\r\n")
        result['start'] = str(startd)
        result['end'] = str(endd)
        result['delta'] = str(delta)

    changed = False

    name_to_device_mappings = list_mappings()
    if name in name_to_device_mappings:
        if state == 'absent':
            sh("rbd unmap " + name_to_device_mappings[name]['device'])
            result['rbd_mappings'] = list_mappings()
            changed = name not in result['rbd_mappings']
    else:
        if state == 'present':
            cmd = "rbd map " + name
            if pool:
                cmd = cmd + " --pool " + pool
            sh(cmd)
            result['rbd_mappings'] = list_mappings()
            changed = name in result['rbd_mappings']

    result['changed'] = changed
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
