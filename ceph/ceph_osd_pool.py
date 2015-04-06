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
module: ceph_osd_pool
short_description: Ceph pools module for Ansible.
description:
 - Use this module to manage Ceph pools
version_added: "1.8"
options:
    name:
        required: true
        description:
            - The name of the pool to create or delete.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Whether the pool should be present or not on the remote host.
    pgnum:
        required: false
        description:
            - Required for C(state=present). The total number of placement groups for the pool.
    pgpnum:
        required: false
        description:
            - Required for C(type=erasure) or when C(ruleset) is specified. The total number of placement
              groups for placement purposes. This should be equal to the total number of placement groups,
              except for placement group splitting scenarios. Picks up default or Ceph configuration value
              if not specified.
    type:
        required: false
        default: "replicated"
        choices: [ "replicated", "erasure" ]
        description:
            - The pool type which may either be C(replicated) to recover from lost OSDs by keeping
              multiple copies of the objects or C(erasure) to get a kind of generalized RAID5 capability.
              The C(replicated) pools require more raw storage but implement all Ceph operations.
              The C(erasure) pools require less raw storage but only implement a subset of the available operations.
    ruleset:
        required: false
        description:
            - The name of the crush ruleset for this pool. If specified ruleset doesn’t exist, the creation of
              C(replicated) pool will fail with C(-ENOENT).

requirements:
 - ceph
author: Alistair Israel
'''

EXAMPLES = '''
# Create a pool
- ceph_osd_pool: state=present name=data pgnum=128 pgpnum=128
'''

import datetime
import json

import rados


def main():
    module = AnsibleModule(
        argument_spec = dict(
            state = dict(choices=['present', 'absent'], default='present'),
            name = dict(required=True),
            pgnum = dict(type='int'),
            pgpnum = dict(type='int'),
            type = dict(choices=['replicated', 'erasure'], default='replicated'),
            ruleset = dict()
        ),
        supports_check_mode = False
    )

    name = module.params['name']

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
        result['stderr'] = err.rstrip("\r\n")
        result['start'] = str(startd)
        result['end'] = str(endd)
        result['delta'] = str(delta)

    changed = False

    with rados.Rados(conffile='/etc/ceph/ceph.conf') as cluster:
        pools = cluster.list_pools()

        state = module.params['state']
        if state == 'present':
            if name not in pools:
                pgnum = module.params['pgnum']
                if not pgnum:
                    module.fail_json(msg='pgnum is required when state=present')
                pgpnum = module.params['pgpnum']
                type = module.params['type']
                ruleset = module.params['ruleset']

                base_cmd = 'ceph osd pool create {0} {1}'

                if ruleset:
                    if not pgpnum:
                        module.fail_json(msg='pgpnum is required when ruleset specified')

                if type == 'erasure':
                    if not pgpnum:
                        module.fail_json(msg='pgpnum is required when type=erasure')
                    cmd = (base_cmd + ' {2} erasure').format(name, pgnum, pgpnum)
                    if ruleset:
                        cmd = cmd + ' ' + ruleset
                else:
                    if ruleset:
                        cmd = (base_cmd + ' {2} replicated {3}').format(name, pgnum, pgpnum, ruleset)
                    elif pgpnum:
                        cmd = (base_cmd + ' {2}').format(name, pgnum, pgpnum)
                    else:
                        cmd = base_cmd.format(name, pgnum)

                sh(cmd)

                expected_stderr = "pool '{0}' created".format(name)
                changed = expected_stderr == result['stderr']
        else:
            if name in pools:
                sh('ceph osd pool delete {0} {0} --yes-i-really-really-mean-it'.format(name))

                expected_stderr = "pool '{0}' removed".format(name)
                changed = expected_stderr == result['stderr']

    result['changed'] = changed
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
