#!/usr/bin/env python3

# pylint: disable=line-too-long

import argparse
import logging
import os
import socket
import subprocess
import time
import uuid
from string import Template

import yaml

# console logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
# Remove all handlers associated with the root logger object so we can start over with an entirely fresh log configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

log_level = logging.INFO
ch = logging.StreamHandler()
ch.setLevel(log_level)
formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
formatter.converter = time.gmtime
ch.setFormatter(formatter)
logging.root.addHandler(ch)

logger = logging.getLogger("es_bench_controller")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", help="Benchmark suites to execute (default: all)", type=str, required=False)

    return parser.parse_args()


def to_list(a):
    return a.split(",") if a else []


def execute_command(cmd_template, template_vars=None):
    command_template = Template(cmd_template)
    if template_vars is None:
        template_vars = {}
    command = command_template.substitute(template_vars)
    exit_code = subprocess.run(command, shell=True, check=False)
    if exit_code.returncode != 0:
        logger.error("[%s] returned with exit code [%s]", command, exit_code)
        raise RuntimeError(f"Executing [{command}] has failed.")


def main():
    args = parse_args()
    included_suites = to_list(args.suites)

    # referenced later by esrally experiments
    with open(os.path.expanduser("~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml")) as file:
        inventory_private = yaml.load(file, Loader=yaml.FullLoader)

    _rally_hosts = inventory_private["all"]["children"]["rally"]["children"]["rally_all"]["hosts"].keys()
    _load_driver_hosts = ["127.0.0.1"] if len(_rally_hosts) == 1 else list(_rally_hosts)
    load_driver_hosts = ",".join(_load_driver_hosts)
    logger.info("Using loaddriver hosts: [%s].", load_driver_hosts)

    # referenced later by rally daemon start
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # get private IP of this host; this will be 127.0.0.1 when there is only one load driver
    sock.connect((_load_driver_hosts[0], 22))
    coordinator_host = sock.getsockname()[0]

    # daemon started here instead of inside fixture to allow rally experiments print results to stdout
    subprocess.run("killall -9 esrallyd", shell=True, check=False)
    command = f"esrallyd start --node-ip={coordinator_host} --coordinator-ip={coordinator_host}"
    execute_command(command)

    logger.info("Executing benchmark suites for use-case [simple] with flavor [].")

    if not included_suites or "simple" in included_suites:
        logger.info("Executing benchmark suite [simple].")
        # Setup for suite simple

        try:
            installation_id = uuid.uuid4()
            logger.info("Using installation id: [%s].", installation_id)
            execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/drop-caches.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
            execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/trim-disks.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
            execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/start-rallyd.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
            try:
                # Benchmark setup
                # referenced later by elasticsearch start fixture and esrally experiments
                race_id = uuid.uuid4()
                logger.info("Using race id: [%s].", race_id)
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/wait-raid-recovery.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/install-elasticsearch.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/start-elasticsearch.yml --extra-vars='"'"'{"is_teardown": false, "telemetry": ["gc"], "telemetry_params": {}, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/start-metricbeat.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/start-filebeat.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/start-kibana.yml --extra-vars='"'"'{"is_teardown": false, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                # Benchmark experiment
                execute_command('esrally race --track-repository=achuguy --pipeline=benchmark-only --track-repository="default" --track="elastic/security" --challenge="security-indexing" --on-error="abort" --target-hosts=~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/simple-experiment-0-target-hosts.json --client-options=~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/simple-experiment-0-client-options.json --track-params=~/track-params-logsdb-endpoint.json --telemetry-params=~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/simple-experiment-0-telemetry-params.json --user-tags=~/user-tags-logsdb-endpoint.json --race-id=$race_id --load-driver-hosts=$load_driver_hosts', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,})
            finally:
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/stop-kibana.yml --extra-vars='"'"'{"is_teardown": true, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/stop-elasticsearch.yml --extra-vars='"'"'{"is_teardown": true, "preserve_elasticsearch_install": true, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/stop-metricbeat.yml --extra-vars='"'"'{"is_teardown": true, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})
                execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/stop-filebeat.yml --extra-vars='"'"'{"is_teardown": true, "provider": "gcp"}'"'"' --extra-vars='"'"'{"race_id":$race_id}'"'"' --extra-vars='"'"'{"load_driver_hosts":$load_driver_hosts}'"'"' --extra-vars='"'"'{"installation_id":$installation_id}'"'"'', {'race_id': race_id,'load_driver_hosts': load_driver_hosts,'installation_id': installation_id,})

        finally:
            execute_command('ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i ~/.esbench/environments/2b61c966-3992-4077-9a3c-34c913087d16/ansible/inventory-private-ip.yaml ansible/playbooks/stop-rallyd.yml --extra-vars='"'"'{"is_teardown": true, "provider": "gcp"}'"'"'', {})
        logger.info("Finished executing benchmark suite [simple].")
    else:
        logger.info("Skipping benchmark suite [simple].")


if __name__ == '__main__':
    main()
