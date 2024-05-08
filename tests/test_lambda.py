import json
import pytest
from moto import mock_aws
import boto3
from src.versioning import create_app, get_version, bump_version, set_version

@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    yield
    os.environ.pop('AWS_ACCESS_KEY_ID', None)
    os.environ.pop('AWS_SECRET_ACCESS_KEY', None)
    os.environ.pop('AWS_SECURITY_TOKEN', None)
    os.environ.pop('AWS_SESSION_TOKEN', None)

@pytest.fixture(scope="function")
def dynamo_db(aws_credentials):
    """Fixture to setup and teardown DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        # Table setup logic here
        yield dynamodb

@mock_aws
def test_create_app():
    """Tests creating an app using the mock_aws decorator."""
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    # Your DynamoDB table setup and test execution logic here
    response = create_app("TestApp")
    assert json.loads(response['body']) == 'App created with version 0.1.0'
    assert response['statusCode'] == 201

# Apply @mock_aws to other test functions similarly
