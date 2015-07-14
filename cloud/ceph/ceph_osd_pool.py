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
version_added: "1.9"
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
    erasure_code_profile:
        required: false
        description:
            - For C(erasure) pools only. Use the specified erasure code profile, which must be an existing profile
              as defined by C(osd erasure-code-profile set).
    ruleset:
        required: false
        description:
            - The name of the crush ruleset for this pool. If specified ruleset doesn’t exist, the creation of
              C(replicated) pool will fail with C(-ENOENT).
    client_name:
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
# Create a pool
- ceph_osd_pool: state=present name=data pgnum=128 pgpnum=128
# Create an erasure coded pool_type and specify erasure_code_profile as well as crush ruleset
- ceph_osd_pool: name=ecpool pgnum=32 pgpnum=32 type=erasure erasure_code_profile=default ruleset=erasure-code
'''

import datetime
import json

import rados
from ceph_argparse import json_command

def main():
    module = AnsibleModule(
        argument_spec = dict(
            state =                 dict(choices=['present', 'absent'], default='present'),
            name =                  dict(required=True),
            pgnum =                 dict(type='int'),
            pgpnum =                dict(type='int'),
            type =                  dict(choices=['replicated', 'erasure'], default='replicated'),
            erasure_code_profile =  dict(),
            ruleset =               dict(),
            client_name =           dict(default="client.admin"),
            cluster =               dict(default="ceph"),
            conf =                  dict(default=""),
            connect_timeout =       dict(type="int", default=5),
        ),
        supports_check_mode = False
    )

    name = module.params['name']

    startd = datetime.datetime.now()
    result = dict(
        name = name,
        start = str(startd)
    )

    changed = False

    client_name = module.params["client_name"]
    cluster_name = module.params["cluster"]
    conffile = module.params["conf"]

    try:
        cluster_handle = rados.Rados(name=client_name, clustername=cluster_name,
                                     conffile=conffile)
    except rados.Error as e:
        module.fail_json(msg="Error initializing cluster client: {0}".format(repr(e)))

    try:
        timeout = module.params['connect_timeout']
        cluster_handle.connect(timeout=timeout)
    except Exception as e:
        module.fail_json(msg="Error connecting to cluster: {0}".format(e.__class__.__name__))

    try:
        pools = cluster_handle.list_pools()

        state = module.params['state']
        if state == 'present':
            if name not in pools:
                pg_num = module.params['pgnum']
                if not pg_num:
                    module.fail_json(msg='pgnum is required when state=present')
                pgp_num = module.params['pgpnum']
                pool_type = module.params['type']
                ruleset = module.params['ruleset']
                erasure_code_profile = module.params['erasure_code_profile']
                # unused expected_num_objects

                args = {
                    'prefix': 'osd pool create',
                    'pool': name,
                    'pool_type': pool_type,
                    'pg_num': pg_num
                }

                if ruleset and not pgp_num:
                    module.fail_json(msg='pgpnum is required when ruleset specified')
                if pool_type == 'erasure':
                    if not pgp_num:
                        module.fail_json(msg='pgpnum is required when type=erasure')
                    args['pgp_num'] = pgp_num
                    if erasure_code_profile:
                        args['erasure_code_profile'] = erasure_code_profile
                    if ruleset:
                        args['ruleset'] = ruleset
                # pool_type = 'replicated'
                else:
                    if ruleset:
                        args['erasure_code_profile'] = ruleset
                    if pgp_num:
                        args['pgp_num'] = pgp_num

                target = ("mon", "")

                rc, outbuf, outs = json_command(cluster_handle, target=target, argdict=args)

                if rc:
                    module.fail_json(msg="Error: {0} {1}".format(rc, errno.errorcode[rc]))

                expected_outs = "pool '{0}' created".format(name)
                changed = expected_outs == outs
                result['outbuf'] = outbuf
                result['outs'] = outs
        else:
            if name in pools:
                target = ("mon", "")
                args = {
                    'prefix': 'osd pool delete',
                    'pool': name,
                    'pool2': name,
                    'sure': '--yes-i-really-really-mean-it'
                }
                rc, outbuf, outs = json_command(cluster_handle, target=target, argdict=args)

                if rc:
                    module.fail_json(msg="Error: {0} {1}".format(rc, errno.errorcode[rc]))

                expected_outs = "pool '{0}' removed".format(name)
                changed = expected_outs == outs
                result['outbuf'] = outbuf
                result['outs'] = outs

        endd = datetime.datetime.now()
        result['end'] = str(endd)
        result['delta'] = str(endd - startd)
        result['changed'] = changed
        module.exit_json(**result)

    finally:
        cluster_handle.shutdown()

# import module snippets
from ansible.module_utils.basic import *
main()
