# VersionVault

## Cloud-Based Semantic Versioning as a Service

VersionVault is a cloud-based service designed to manage semantic versioning of your applications easily. It utilizes AWS Serverless architecture, providing a scalable, reliable, and secure platform for version management.

### Features

- **Create Versioned Apps**: Start version tracking for new applications by creating them through the API.
- **Bump Versions**: Easily bump the semantic version of your applications (major, minor, patch).
- **Set Specific Version**: Directly set a specific version for an application.
- **Retrieve Version**: Get the current version of any registered application.
- **Security**: Secure version management with optional token-based authentication for each app.

### Architecture

VersionVault utilizes AWS Lambda, DynamoDB, and API Gateway to offer a fully managed serverless solution. Static content, like API documentation, is hosted on S3.

### Components

- **AWS Lambda**: Handles the backend logic.
- **AWS API Gateway**: Manages and routes API requests.
- **AWS DynamoDB**: Stores app data and version information.
- **AWS S3**: Hosts the static HTML documentation site.

### API Endpoints

#### Create Application

- **POST** `/create` - Creates a new application entry in VersionVault.

#### Get Current Version

- **GET** `/{app_name}/version` - Retrieves the current version of the specified app.

#### Bump Version

- **POST** `/{app_name}/bump` - Bumps the specified type of version (patch, minor, major) for an app.

#### Set Version

- **POST** `/{app_name}/set` - Sets a specific version for an app.

### Examples

# Creating a secure application named "myApp"

curl -X POST "http://<your-api-endpoint>/create?app_name=myApp&secure=true"

# Response will look like this with a token

# {"app_name": "myApp", "version": "0.1.0", "token": "<token>"}

# Getting the current version of "myApp"

curl -X GET "http://<your-api-endpoint>/myApp/version" -H "Authorization: <token>"

# Bumping the major version of "myApp"

curl -X POST "http://<your-api-endpoint>/myApp/bump?type=major" -H "Authorization: <token>"

# Setting a specific version (e.g., 2.5.1) for "myApp"

curl -X POST "http://<your-api-endpoint>/myApp/set?new_version=2.5.1" -H "Authorization: <token>"

### Setup and Deployment

Follow these steps to deploy VersionVault:

1. **Prerequisites**:
   - AWS CLI installed and configured.
   - AWS SAM CLI installed.
2. **Deployment**:
   - Navigate to the project directory.
   - Run `sam build` to build the application.
   - Deploy the application using `sam deploy --guided`.
