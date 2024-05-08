#!/bin/bash

# Start DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local -jar DynamoDBLocal.jar -sharedDb &

# Wait for DynamoDB to start
sleep 3

# Create DynamoDB table locally
aws dynamodb create-table --table-name VersioningApp \
    --attribute-definitions AttributeName=appName,AttributeType=S \
    --key-schema AttributeName=appName,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000

# Set environment variables for local testing
cat > env.json <<EOL
{
  "VersioningFunction": {
    "TABLE_NAME": "VersioningApp",
    "IS_LOCAL": "true",
    "DYNAMODB_ENDPOINT": "http://host.docker.internal:8000",
    "SECRET_KEY": "local_secret_key",
    "AWS_ACCESS_KEY_ID": "fakeMyKeyId",
    "AWS_SECRET_ACCESS_KEY": "fakeSecretAccessKey"
  }
}
EOL

# Start local API Gateway simulation
sam local start-api --env-vars env.json