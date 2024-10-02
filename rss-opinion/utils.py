""" Useful functions to perform the common processes """
#pylint: disable=E0401,E0611
import json
import logging
import colorlog
from google.cloud import secretmanager, storage
from google.oauth2 import service_account
#-------------------------------------------------------------------------------------
# Basic Logging configuration
#-------------------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a handler
handler = logging.StreamHandler()

# Define color format
formatter = colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
)

# Add the formatter to the handler
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

#-------------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------------

def get_secret(desired_key: str, project_name: str = "rss-opinion") -> str: #pylint: disable=W0613
    """ Get a secret from the google secret manager.

    Args:
        desired_key (str): The key of the secret you want to get.
        project_name (str): The name of your google cloud project

    Returns:
        str: The value of the secret.
    """
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f'projects/1023482698266/secrets/{desired_key}/versions/latest'
    response = client.access_secret_version(request={"name": secret_name})

    secret_string = response.payload.data.decode('UTF-8')
    if desired_key == "GCP_API_TOKEN":
        service_account_info = json.loads(secret_string)
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return credentials
    return response.payload.data.decode('UTF-8')



def download_latest_blob(bucket_name: str, folder_prefix: str, local_blob_name: str) -> str:
    """
    Downloads the latest uploaded blob from a specified folder in the bucket to a local file,
    filtering by blob name.
    Returns the path to the local XML file to be processed.
    If no matching blobs are found, logs that the provided XML is a dummy XML and uses
    'resources/dummy.xml'.

    Parameters:
    - bucket_name: Name of the GCS bucket.
    - folder_prefix: The folder path within the bucket to search for blobs.
    - local_blob_name: Local path where the blob will be saved if found.
    - name_filter: An optional callable that takes a blob name and returns True if the blob should
    be considered.

    Returns:
    - xml_file_path: The path to the XML file to be processed.
    """
    # Create credentials using the service account key file or secret manager
    project = "rss-opinion"
    credentials = get_secret("GCP_API_TOKEN", project)

    # Initialize a client with the credentials
    storage_client = storage.Client(credentials=credentials)
    # storage_client = storage.Client.from_service_account_json("../rss-opinion-credentials.json")
    # Retrieve the bucket
    bucket = storage_client.bucket(bucket_name)

    # List all blobs in the specified folder
    blobs = list(bucket.list_blobs(prefix=folder_prefix))

    if not list(blobs):

        logger.info(
            "No  blobs found in the folder '%s' in bucket '%s'.",
            folder_prefix,
            bucket_name
        )

        # Use the dummy XML file
        dummy_xml_path = 'resources/dummy.xml'
        logger.info("Using dummy XML file at '%s'.", dummy_xml_path)

        # Return the path to the dummy XML file
        return dummy_xml_path

    # Find the latest blob based on the updated time
    latest_blob = max(blobs, key=lambda b: b.updated)

    # Download the latest blob to a local file
    latest_blob.download_to_filename(local_blob_name)


    # Return the path to the local XML file
    return local_blob_name



def upload_blob(bucket_name, bucket_blob_name, local_blob_name):
    """
    Uploads a local file to a blob in the bucket, using explicit authentication.
    
    Parameters:
    - bucket_name: Name of the GCS bucket.
    - bucket_blob_name: Path where the blob will be stored in the bucket.
    - local_blob_name: Local path of the file to be uploaded.
    """
    # Create credentials using the service account key file or secret manager
    project = "rss-opinion"
    credentials = get_secret("GCP_API_TOKEN", project)

    # Initialize a client with the credentials
    storage_client = storage.Client(credentials=credentials)
    # storage_client = storage.Client.from_service_account_json("../rss-opinion-credentials.json")

    # Retrieve the bucket
    bucket = storage_client.bucket(bucket_name)

    # Create a new blob in the bucket
    blob = bucket.blob(f'{bucket_blob_name}.xml')

    # Upload the local file to the blob
    blob.upload_from_filename(local_blob_name)

    print(f"File '{local_blob_name}' uploaded to '{bucket_blob_name}'.")

# Usage
# if __name__ == "__main__":
#     bucket_name = "your-bucket-name"
#     bucket_blob_name = "path/to/your/blob"  # The path to your object in the bucket
#     local_blob_name = "local/path/to/file.ext"
#     key_path = "path/to/your/service-account-key.json"

#     download_blob(bucket_name, bucket_blob_name, local_blob_name, key_path)
