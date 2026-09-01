from __future__ import annotations

from pathlib import Path

import paramiko


KNOWN_HOSTS = Path.home() / ".ssh" / "known_hosts"


def create_ssh_client(trust_new_host_key: bool) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if KNOWN_HOSTS.is_file():
        client.load_host_keys(str(KNOWN_HOSTS))
    policy = paramiko.AutoAddPolicy() if trust_new_host_key else paramiko.RejectPolicy()
    client.set_missing_host_key_policy(policy)
    return client


def persist_host_keys(client: paramiko.SSHClient, trust_new_host_key: bool) -> None:
    if not trust_new_host_key:
        return
    KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
    client.save_host_keys(str(KNOWN_HOSTS))
