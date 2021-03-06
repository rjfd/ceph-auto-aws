#
# Copyright (c) 2016, SUSE LLC All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# * Neither the name of ceph-auto-aws nor the names of its contributors may be
# used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import argparse
import handson.myyaml
import logging
import textwrap

from boto import connect_ec2
from handson.delegate import Delegate
from handson.misc import (
    CustomFormatter,
    InitArgs,
)
from handson.parsers import (
    cluster_options_parser,
    subcommand_parser,
    subcommand_parser_with_retag
)
from handson.region import Region
from handson.subnet import Subnet
from handson.vpc import VPC

log = logging.getLogger(__name__)


class Probe(object):

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(
            usage='ho probe',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Probe AWS connection and cluster configuration.

            The documentation for each sub-subcommand can be displayed with

               ho probe sub-subcommand --help

            For instance:

               ho probe aws --help
               usage: ho probe aws [-h]
               ...

            For more information, refer to the README.rst file at
            https://github.com/smithfarm/ceph-auto-aws/README.rst
            """))

        subparsers = parser.add_subparsers(
            title='probe subcommands',
            description='valid probe subcommands',
            help='probe subcommand -h',
        )

        subparsers.add_parser(
            'aws',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Probe AWS (test ability to connect to EC2).

            Once you have set up your AWS credentials in ~/.boto,
            run this subcommand to check connectivity.
            """),
            epilog=textwrap.dedent("""
            Example:

            $ ho probe aws
            $ echo $?
            0

            """),
            help='Test ability to connect to AWS EC2',
            parents=[subcommand_parser()],
            add_help=False,
        ).set_defaults(
            func=ProbeAWS,
        )

        subparsers.add_parser(
            'delegates',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Probe delegates (number of instances in subnet).

            """),
            epilog=textwrap.dedent("""
            Example:

            $ ho probe delegates
            $ echo $?
            0

            """),
            help='Print number of instances in each subnet',
            parents=[cluster_options_parser()],
            add_help=False,
        ).set_defaults(
            func=ProbeDelegates,
        )

        subparsers.add_parser(
            'public-ips',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            List public IPs in a special format

            """),
            epilog=textwrap.dedent("""
            Example:

            $ ho probe public-ips
            $ echo $?
            0

            """),
            help='List public IP addresses in special format',
            parents=[cluster_options_parser()],
            add_help=False,
        ).set_defaults(
            func=ProbePublicIPs,
        )

        subparsers.add_parser(
            'region',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Test connect to the region defined in YAML.

            This subcommand reads the "region" stanza of the YAML
            file to determine which region to connect to. Then it
            attempts to open a connection to the VPC service in that
            region.
            """),
            epilog=textwrap.dedent("""
            Example:

            $ ho probe region
            $ echo $?
            0

            """),
            help='Test region connectivity',
            parents=[subcommand_parser()],
            add_help=False,
        ).set_defaults(
            func=ProbeRegion,
        )

        subparsers.add_parser(
            'subnets',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Probe subnets and create them if they are missing.

            This subcommand checks that each delegate has a subnet in AWS VPC,
            in accordance with the 'delegate' stanza of the YaML. If any subnet
            is missing, it is created and the YaML is updated.

            It also checks the Salt Master's dedicated subnet and creates it if
            necessary.

            """),
            epilog=textwrap.dedent(""" Examples:

            $ ho probe subnets
            $ echo $?
            0

            """),
            help='Probe subnets and create if missing',
            parents=[subcommand_parser_with_retag()],
            add_help=False,
        ).set_defaults(
            func=ProbeSubnets,
        )

        subparsers.add_parser(
            'vpc',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Probe VPC and create one if it is missing.

            This subcommand checks the VPC status in AWS, compares it with the
            YaML. If VPC is missing in AWS, it is created and the YaML is
            updated.

            """),
            epilog=textwrap.dedent(""" Examples:

            $ ho probe vpc
            $ echo $?
            0

            """),
            help='Probe VPC and create if missing',
            parents=[subcommand_parser_with_retag()],
            add_help=False,
        ).set_defaults(
            func=ProbeVPC,
        )

        subparsers.add_parser(
            'yaml',
            formatter_class=CustomFormatter,
            description=textwrap.dedent("""\
            Validate YaML file.

            Use this subcommand to validate the yaml file.
            """),
            epilog=textwrap.dedent("""
            Examples:

            $ ho probe yaml
            $ echo $?
            0

            $ ho --yamlfile bogus probe-yaml
            ... tracebacks ...
            $ echo $?
            1

            """),
            help='Probe YaML file',
            parents=[subcommand_parser()],
            add_help=False,
        ).set_defaults(
            func=ProbeYaml,
        )

        return parser


class ProbeAWS(InitArgs):

    def run(self):
        connect_ec2()
        log.info("Connected to AWS EC2")


class ProbeDelegates(InitArgs):

    def __init__(self, args):
        super(ProbeDelegates, self).__init__(args)
        self.args = args

    def run(self):
        delegates = handson.myyaml.stanza('delegates')
        for d in range(0, delegates + 1):
            delegate_obj = Delegate(self.args, d)
            delegate_obj.probe()


class ProbePublicIPs(InitArgs):

    def __init__(self, args):
        super(ProbePublicIPs, self).__init__(args)
        self.args = args

    def run(self):
        level = logging.WARNING
        logging.getLogger('handson').setLevel(level)
        delegates = handson.myyaml.stanza('delegates')
        for d in range(0, delegates + 1):
            delegate_obj = Delegate(self.args, d)
            public_ips = delegate_obj.public_ips()
            if public_ips is None:
                continue
            if 'admin' in public_ips:
                print ("Delegate {}, role {}, public IP {}"
                       .format(d, 'admin', public_ips['admin']))
            if 'windows' in public_ips:
                print ("Delegate {}, role {}, public IP {}"
                       .format(d, 'windows', public_ips['admin']))
                print


class ProbeRegion(InitArgs):

    def __init__(self, args):
        super(ProbeRegion, self).__init__(args)
        self.region = handson.myyaml.stanza('region')
        self.args = args

    def run(self):
        log.info("Testing connectivity to AWS Region {!r}"
                 .format(self.region))
        r = Region(self.args)
        vpc_conn = r.vpc()
        vpc_count = len(vpc_conn.get_all_vpcs())
        log.info("Detected {!r} VPCs".format(vpc_count))
        az = r.availability_zone()
        if az:
            log.info("Availability zone explicitly set to {}"
                     .format(az))
            ec2 = r.ec2()
            if ec2.get_all_zones(zones=[az]):
                log.info("Availability zone is OK")
            else:
                log.info("Availability zone is NOT OK!!!")
        else:
            log.info("Availability zone not set in YAML")


class ProbeSubnets(InitArgs):

    def __init__(self, args):
        super(ProbeSubnets, self).__init__(args)
        self.args = args

    def run(self):
        delegates = handson.myyaml.stanza('delegates')
        log.info('Probing {!r} subnets'.format(delegates + 1))
        for d in range(0, delegates + 1):
            c = Subnet(self.args, d)
            c.subnet_obj(create=False)


class ProbeVPC(InitArgs):

    def __init__(self, args):
        super(ProbeVPC, self).__init__(args)
        self.args = args

    def run(self):
        VPC(self.args).vpc_obj(create=False)


class ProbeYaml(InitArgs):

    def __init__(self, args):
        super(ProbeYaml, self).__init__(args)

    def run(self):
        handson.myyaml.probe_yaml()
