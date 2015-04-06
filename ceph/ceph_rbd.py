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
module: ceph_rbd
short_description: Ceph rbd module for Ansible.
description:
 - Use this module to manage Ceph rbds.
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
            - Whether the rbd should be present or not on the remote host.
    image:
        required: false
        description:
            - Required for C(state=present). The image name to use for the rbd.
    pool:
        required: false
        default: "rbd"
        description:
            - The pool name to use for the rbd operations.
    size:
        required: false
        description:
            - Required for C(state=present). The size of the rbd in MB.
    allow_shrink:
        required: false
        default: "no"
        choices: [ "yes", "no" ]
        description:
            - Optionally when used with the C(size) option, setting this flag to C("yes")
              enables the C(--allow-shrink) flag which allows shrinking of an image when resizing.
    image_format:
        required: false
        choices: [ "1", "2" ]
        description:
            - Specifies which object layout to use. Format C(1) is the original format for a new
              rbd image. This format is understood by all versions of librbd and the kernel rbd
              module, but does not support newer features like cloning. Format C(2) is the second
              rbd format, which is supported by librbd and kernel since version 3.11 (except for
              striping). This adds support for cloning and is more easily extensible to allow
              more features in the future.
    image_shared:
        required: false
        choices: [ "yes", "no" ]
        description:
            - Specifies that the image will be used concurrently by multiple clients. This will
              disable features that are dependent upon exclusive ownership of the image.

requirements:
 - ceph
author: Alistair Israel
'''

EXAMPLES = '''
# Create an rbd image (or enlarge an existing one)
- ceph_rbd: name=rbd1 size=128
# Create an rbd image with a specified format and sharing (needed for mapping in v0.92)
- ceph_rbd: name=rbd2 image_format=2 image_shared=true
# Shrink an existing image, if it exists (otherwise, create one)
- ceph_rbd: name=rbd1 size=32 allow_shrink=true
# Remove an rbd
- ceph_rbd: name=rbd1
'''

import datetime
import json

import rados
import rbd


DEFAULT_POOL = 'rbd'

def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(choices=['present', 'absent'], default='present'),
            name=dict(required=True),
            pool=dict(),
            image=dict(),
            size=dict(type='int'),
            allow_shrink=dict(default='no', type='bool'),
            image_format=dict(choices=["1", "2"], type='int'),
            image_shared=dict(type='bool')
        ),
        supports_check_mode=False
    )

    name = module.params['name']
    state = module.params['state']
    pool = module.params['pool']
    pool_for_open_ioctx = pool if pool else DEFAULT_POOL
    size = module.params['size']

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

    with rados.Rados(conffile="/etc/ceph/ceph.conf") as cluster:
        with cluster.open_ioctx(pool_for_open_ioctx) as ioctx:
            r = rbd.RBD()
            existing_rbd_names = r.list(ioctx)
            rbd_exists = name in existing_rbd_names

            if state == 'present':
                if not size:
                    module.fail_json(msg="size is required when state=present")
                if not rbd_exists:
                    cmd = "rbd create {0} --size {1}".format(name, module.params['size'])
                    if module.params['image_format']:
                        cmd = cmd + " --image-format " + str(module.params['image_format'])
                    if module.params['image_shared']:
                        cmd = cmd + " --image-shared"
                    if pool:
                        cmd = cmd + " --pool " + pool
                    sh(cmd)

                    # check if new rbd created
                    changed = name in r.list(ioctx)
                else:
                    allow_shrink = module.params['allow_shrink']

                    with rbd.Image(ioctx, name, read_only=True) as image:
                        current_size = image.size()

                    new_size = module.params['size'] * 1024 * 1024
                    if new_size < current_size and not allow_shrink:
                        module.fail_json(
                            msg="shrinking an image is only allowed with allow_shrink=\"true\"",
                            name=name,
                            size=size,
                            current_size=current_size
                        )
                    if not new_size == current_size:
                        cmd = "rbd resize --size {1} {0}".format(name, module.params['size'])
                        if allow_shrink:
                            cmd = cmd + " --allow-shrink"
                        if pool:
                            cmd = cmd + " --pool " + pool
                        sh(cmd)

                        if result['stderr'].startswith("\rResizing image"):
                            result['stderr'] = result['stderr'].split('\r')[-1]
                            changed = stderr == "Resizing image: 100% complete...done."

            elif state == 'absent' and rbd_exists:
                if pool:
                    cmd = cmd + " --pool " + pool
                sh("rbd rm " + name)

                if result['stderr'].startswith("\rRemoving image"):
                    result['stderr'] = result['stderr'].split('\r')[-1]
                    changed = stderr == "Removing image: 100% complete...done."

    result['changed'] = changed
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
