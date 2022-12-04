"""
TODO describe this script
"""
import boto3
import botocore
import errno
import io
import os
import re
import requests
from PyPDF2 import PdfFileReader

AWS_ACCESS_KEY_ID = None
AWS_SECRET_ACCESS_KEY = None
RUN_LOCAL = False
if RUN_LOCAL:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")


def find_rob() -> str:
    """
    Validates the link to the current pdf-file of rescued seal pups.
    :return: (str) The url-path to the current pdf-file of rescued seal pups.
    """
    url = "https://www.seehundstation-friedrichskoog.de/wp-content/heuler/1.6HomepageHeuler.pdf"
    response = requests.get(url)
    if response.status_code != 200:
        # TODO send out email notification path to rob no longer valid
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), url)
    return url


def save_rob(url):
    # Create S3-client
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    s3_bucket = "rob-oliver"
    s3_path_data = "data/raw"
    s3_path_changelog = "data/changelog"
    # Get raw data
    response = requests.get(url)
    pdf_file_reader = PdfFileReader(io.BytesIO(response.content))
    # Create file name and -path based on modification date of raw data
    modification_date = re.findall(r"\d+", pdf_file_reader.documentInfo["/ModDate"])[0][
        :8
    ]
    file_name = f"{modification_date}_{os.path.basename(url)}"
    file_path_data = f"{s3_path_data}/{file_name}"
    try:
        s3.get_object(Bucket=s3_bucket, Key=file_path_data)
    except botocore.exceptions.ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchKey":
            # The object does not exist.
            try:
                # Uploads the file to s3
                s3.upload_fileobj(
                    io.BytesIO(response.content), s3_bucket, file_path_data
                )
                s3.put_object(
                    Bucket=s3_bucket, Key=f"{s3_path_changelog}/{file_name[:-3]}log"
                )
                print(f"File downloaded from {url} and uploaded to {file_path_data}")
            except:
                # The upload or logging failed
                print(
                    f"File not uploaded to {os.path.join(s3_bucket, s3_path_data)} in S3 bucket {s3_bucket}."
                )
                raise
        else:
            # Something else has gone wrong.
            print(error)
            raise
    else:
        # The object does exist.
        print("The file already exists.")


def lambda_handler(event, context):
    rob_url = find_rob()
    save_rob(rob_url)
