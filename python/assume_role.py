"""Assume an allowlisted cross-account role without printing credentials."""
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

ROLE = re.compile(r"^arn:(aws|aws-us-gov|aws-cn):iam::([0-9]{12}):role/([A-Za-z0-9_+=,.@/-]+)$")
EXTERNAL = re.compile(r"^[A-Za-z0-9_+=,.@:/-]{2,1224}$")
SDK_CONFIG = Config(retries={"mode": "standard", "max_attempts": 4}, connect_timeout=5, read_timeout=20)

@dataclass(frozen=True)
class Target:
    source_role_arn: str
    role_arn: str
    external_id_env: str
    region: str = "us-east-1"

    def validate(self):
        source, target = ROLE.fullmatch(self.source_role_arn), ROLE.fullmatch(self.role_arn)
        if not source or not target:
            raise ValueError("Both role ARNs must be exact IAM role ARNs")
        if source[1] != target[1] or source[2] == target[2]:
            raise ValueError("Roles must be in different accounts in the same partition")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.external_id_env):
            raise ValueError("Invalid external ID environment variable name")


def verify_identity(identity, role_arn):
    match = ROLE.fullmatch(role_arn)
    expected = f"arn:{match[1]}:sts::{match[2]}:assumed-role/{match[3].split('/')[-1]}/"
    if identity["Account"] != match[2] or not identity["Arn"].startswith(expected):
        raise ValueError("AWS identity does not match the configured role")


def assume(target, session_name, duration=900, source_session=None):
    """Return (boto3 session, expiration); caller credentials use the default chain."""
    target.validate()
    if not re.fullmatch(r"[A-Za-z0-9_+=,.@-]{2,64}", session_name):
        raise ValueError("Session name must be 2-64 valid STS characters")
    if not 900 <= duration <= 3600:
        raise ValueError("Duration must be 900-3600 seconds (role chaining limit)")
    external_id = os.environ.get(target.external_id_env, "")
    if not EXTERNAL.fullmatch(external_id):
        raise ValueError("Missing or invalid external ID environment variable")
    source = source_session or boto3.Session(region_name=target.region)
    sts = source.client("sts", region_name=target.region, config=SDK_CONFIG)
    verify_identity(sts.get_caller_identity(), target.source_role_arn)
    response = sts.assume_role(RoleArn=target.role_arn, ExternalId=external_id,
                               RoleSessionName=session_name, DurationSeconds=duration)
    creds = response["Credentials"]
    session = boto3.Session(aws_access_key_id=creds["AccessKeyId"],
                            aws_secret_access_key=creds["SecretAccessKey"],
                            aws_session_token=creds["SessionToken"], region_name=target.region)
    verify_identity(session.client("sts", config=SDK_CONFIG).get_caller_identity(), target.role_arn)
    return session, creds["Expiration"]


def run_command(session, command):
    if not command:
        raise ValueError("Provide a command after --")
    credentials = session.get_credentials().get_frozen_credentials()
    env = dict(os.environ)
    # Remove competing SDK profile selectors and legacy token aliases.
    for key in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_SECURITY_TOKEN"):
        env.pop(key, None)
    env.update(AWS_ACCESS_KEY_ID=credentials.access_key,
               AWS_SECRET_ACCESS_KEY=credentials.secret_key,
               AWS_SESSION_TOKEN=credentials.token,
               AWS_REGION=session.region_name, AWS_DEFAULT_REGION=session.region_name)
    return subprocess.run(command, env=env, shell=False, check=False).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--session-name", required=True)
    parser.add_argument("--duration", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        entries = json.loads(args.config.read_text())
        target = Target(**entries[args.target])
        session, expiration = assume(target, args.session_name, args.duration)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if command:
            return run_command(session, command)
        print(json.dumps({"role_arn": target.role_arn, "expiration": expiration.isoformat()}))
        return 0
    except ClientError as exc:
        # Do not print request parameters, tokens, or external IDs.
        print(f"AWS request failed: {exc.response['Error']['Code']}", file=sys.stderr)
    except (BotoCoreError, ValueError, KeyError, TypeError, OSError):
        print("Role assumption failed; check configuration, credentials and trust policy", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
