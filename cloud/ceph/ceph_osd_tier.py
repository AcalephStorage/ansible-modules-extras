#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2015, Hunter Nield <hunter@acale.ph>
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
module: ceph_osd_tier
short_description: Ceph Cache Tier module for Ansible.
description:
 - Use this module to manage Ceph Cache Tiers
version_added: "1.9"
options:
    storage_pool:
        required: true
        description:
            - The name of the pool to be used for storage (must already exist)
    cache_pool:
        required: true
        description:
            - The name of the pool to be used for cache (must already exist)
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Whether the Cache Tier should be present on the chosen pools.
    cache_mode:
        required: false
        default: "writeback"
        choices: [ "none", "writeback", "forward", "readonly"]
        description:
            - Sets the cache mode for the cache tier
    set_overlay:
        required: false
        default: "no"
        choices: [ "yes", "no" ]
        description:
            - Sets the Cache Pool to be active
    force_nonempty:
        required: false
        default: "no"
        choices: [ "yes", "no" ]
        description:
            - Use the cache pool even if it contains data

requirements:
 - ceph
author: Hunter Nield
'''

EXAMPLES = '''
# Create a cache tier
- ceph_osd_tier: state=present storage_pool=cold-storage cache_pool=hot-storage

# Create a readonly cache tier and make it active
- ceph_osd_tier: state=present storage_pool=cold-storage cache_pool=hot-storage cache_mode=readonly set_overlay=yes

'''

import datetime
import json

import rados


def main():
    module = AnsibleModule(
        argument_spec = dict(
            state = dict(choices=['present', 'absent'], default='present'),
            storage_pool = dict(required=True),
            cache_pool = dict(required=True),
            cache_mode = dict(choices=['none', 'writeback', 'forward', 'readonly'], default='writeback'),
            set_overlay = dict(default='no', type='bool'),
            force_nonempty = dict(default='no', type='bool'),
        ),
        supports_check_mode = False
    )

    storage_pool = module.params['storage_pool']
    cache_pool = module.params['cache_pool']

    result = {}
    result['storage_pool'] = storage_pool
    result['cache_pool'] = cache_pool

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
            if storage_pool not in pools:
                module.fail_json(msg='storage_pool does not exist')
            if cache_pool not in pools:
                module.fail_json(msg='cache_pool does not exist')

            cmd = 'ceph osd tier add {0} {1}'


            if module.params['force_nonempty'] == True:
                cmd = (cmd + ' --force-nonempty')

            cmd = cmd.format(storage_pool, cache_pool)
            sh(cmd)

            expected_stderr = "pool '{1}' is now (or already was) a tier of '{0}'".format(storage_pool, cache_pool)
            changed = expected_stderr == result['stderr']


            cache_mode = module.params['cache_mode']
            if changed == True:
                sh('ceph osd tier cache-mode {0} {1}'.format(cache_pool, cache_mode))

                expected_stderr = "set cache_mode for pool '{0}' to {1}".format(cache_pool, cache_mode)
                changed = expected_stderr == result['stderr']

            set_overlay = module.params['set_overlay']
            if changed == True:
                if set_overlay == True:
                    sh('ceph osd tier set-overlay {0} {1}'.format(storage_pool, cache_pool))

                    expected_stderr = "overlay for '{0}' is now (or already was) '{1}'".format(storage_pool, cache_pool)
                    changed = expected_stderr == result['stderr']
                else:
                    sh('ceph osd tier remove-overlay {0}'.format(cache_pool))

                    expected_stderr = "there is now (or already was) no overlay for '{0}'".format(cache_pool)
                    changed = expected_stderr == result['stderr']

        else:
            if storage_pool not in pools:
                module.fail_json(msg='storage_pool does not exist')
            if cache_pool not in pools:
                module.fail_json(msg='cache_pool does not exist')

            # Idempotent. Run to make sure we don't have it active already
            sh('ceph osd tier remove-overlay {0}'.format(cache_pool))

            expected_stderr = "there is now (or already was) no overlay for '{0}'".format(storage_pool)
            changed = expected_stderr == result['stderr']

            sh('ceph osd tier remove {0} {1}'.format(storage_pool, cache_pool))

            expected_stderr = "pool '{1}' is now (or already was) not a tier of '{0}'".format(storage_pool, cache_pool)
            changed = expected_stderr == result['stderr']

    result['changed'] = changed
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
