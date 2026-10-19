import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import boto3
import pytest
from botocore.stub import Stubber

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from assume_role import Target, assume, run_command, verify_identity

SOURCE = 'arn:aws:iam::111111111111:role/team/pipeline'
DEST = 'arn:aws:iam::222222222222:role/deploy'
TARGET = Target(SOURCE, DEST, 'CICD_EXTERNAL_ID')

def identity(account, role):
    return {'Account': account, 'Arn': f'arn:aws:sts::{account}:assumed-role/{role}/test', 'UserId': 'id:test'}

@pytest.fixture
def sts():
    return boto3.client('sts', region_name='us-east-1', aws_access_key_id='testing', aws_secret_access_key='testing')

def test_assume_verified_and_exact_parameters(sts, monkeypatch):
    monkeypatch.setenv('CICD_EXTERNAL_ID', 'unique-external-id')
    expiration = datetime(2030, 1, 1, tzinfo=timezone.utc)
    response = {'Credentials': {'AccessKeyId': 'ASIA' + 'A' * 16, 'SecretAccessKey': 's' * 40,
                 'SessionToken': 'token', 'Expiration': expiration},
                'AssumedRoleUser': {'AssumedRoleId': 'id:test', 'Arn': 'arn:aws:sts::222222222222:assumed-role/deploy/test'}}
    source = Mock()
    source.client.return_value = sts
    dest = Mock()
    dest.client.return_value.get_caller_identity.return_value = identity('222222222222', 'deploy')
    with Stubber(sts) as stub, patch('assume_role.boto3.Session', return_value=dest) as factory:
        stub.add_response('get_caller_identity', identity('111111111111', 'pipeline'), {})
        stub.add_response('assume_role', response, {'RoleArn': DEST, 'ExternalId': 'unique-external-id',
                          'RoleSessionName': 'build-123', 'DurationSeconds': 900})
        session, expires = assume(TARGET, 'build-123', source_session=source)
        assert session is dest and expires == expiration
        assert factory.call_args.kwargs['aws_session_token'] == 'token'
        stub.assert_no_pending_responses()

@pytest.mark.parametrize('duration', [0, 899, 3601, 7200])
def test_invalid_duration(duration, monkeypatch):
    monkeypatch.setenv('CICD_EXTERNAL_ID', 'unique')
    with pytest.raises(ValueError):
        assume(TARGET, 'build-123', duration, Mock())

@pytest.mark.parametrize('name', ['x', 'bad space', 'a' * 65])
def test_invalid_session(name):
    with pytest.raises(ValueError):
        assume(TARGET, name, source_session=Mock())

def test_missing_external_id_fails_before_aws(monkeypatch):
    monkeypatch.delenv('CICD_EXTERNAL_ID', raising=False)
    source = Mock()
    with pytest.raises(ValueError):
        assume(TARGET, 'build-123', source_session=source)
    source.client.assert_not_called()

def test_wrong_source_fails_before_assumption(monkeypatch):
    monkeypatch.setenv('CICD_EXTERNAL_ID', 'unique')
    source = Mock()
    source.client.return_value.get_caller_identity.return_value = identity('111111111111', 'other-role')
    with pytest.raises(ValueError):
        assume(TARGET, 'build-123', source_session=source)
    source.client.return_value.assume_role.assert_not_called()

@pytest.mark.parametrize('account,role', [('333333333333', 'deploy'), ('222222222222', 'deploy-extra')])
def test_wrong_target_identity(account, role):
    with pytest.raises(ValueError):
        verify_identity(identity(account, role), DEST)

@pytest.mark.parametrize('dest', ['arn:aws:iam::222222222222:role/*', SOURCE,
                                'arn:aws-cn:iam::222222222222:role/deploy', 'invalid'])
def test_invalid_target(dest):
    with pytest.raises(ValueError):
        Target(SOURCE, dest, 'EXT_ID').validate()

def test_aws_denial_is_propagated(sts, monkeypatch):
    from botocore.exceptions import ClientError
    monkeypatch.setenv('CICD_EXTERNAL_ID', 'unique')
    source = Mock()
    source.client.return_value = sts
    with Stubber(sts) as stub:
        stub.add_response('get_caller_identity', identity('111111111111', 'pipeline'), {})
        stub.add_client_error('assume_role', 'AccessDenied')
        with pytest.raises(ClientError):
            assume(TARGET, 'build-123', source_session=source)
        stub.assert_no_pending_responses()

def test_child_env_credentials_and_exit_code(monkeypatch):
    monkeypatch.setenv('AWS_PROFILE', 'wrong-profile')
    session = Mock(region_name='us-east-1')
    session.get_credentials.return_value.get_frozen_credentials.return_value = Mock(access_key='new-key', secret_key='new-secret', token='new-token')
    with patch('assume_role.subprocess.run') as run:
        run.return_value.returncode = 17
        assert run_command(session, ['aws', 'sts', 'get-caller-identity']) == 17
        env = run.call_args.kwargs['env']
        assert 'AWS_PROFILE' not in env
        assert env['AWS_SESSION_TOKEN'] == 'new-token'
        assert run.call_args.kwargs['shell'] is False
