import logging
from io import StringIO

import boto3
import json
from typing import Any, Dict, List
from botocore.exceptions import ClientError
logger = logging.getLogger("jetbrains.com-data")
logger.setLevel(logging.INFO)
logger.debug("main message")

class S3:
    """
    A class to manage operations with AWS S3.
    """

    def __init__(self, bucket) -> None:
        """
        Initialize the S3Manager object.
        """
        self.s3_client = boto3.client('s3')
        self.s3_resource = boto3.resource('s3')
        self.bucket = bucket

    def download_file(self, object_name: str, file_name: str) -> None:
        """
        Download a file from an S3 bucket.

        Args:
            bucket: The bucket to download from.
            object_name: The object to download.
            file_name: The file to save the object to.

        Returns:
            None
        """
        self.s3_client.download_file(self.bucket, object_name, file_name)

    def list_objects(self) -> Dict[str, Any]:
        """
        TODO : not in use - use instead get_s3_list_of_files
        List objects in an S3 bucket.

        Args:
            bucket: The bucket to list objects in.

        Returns:
            The list of objects in the bucket.
        """
        response = self.client.list_objects_v2(Bucket=self.bucket)
        return response

    def read_json_s3_object(self, object_name):
        obj = self.s3_resource.Object(self.bucket, object_name)
        content = obj.get()['Body'].read()
        content_str = content.decode('utf-8')  # Convert bytes to string
        content_dict = json.loads(content_str)  # Parse JSON string to dictionary
        return content_dict[0]

    def read_object(self, object_name: str) -> bytes:
        """
        Get an object from an S3 bucket.

        Args:
            object_name: The object name.

        Returns:
            The object's content as bytes.
        """
        content = None
        try:
            obj = self.s3_resource.Object(self.bucket, object_name)
            content = obj.get()['Body'].read()
            # content_str = content.decode('utf-8')  # Convert bytes to string
        except Exception as e:
            logger.error(f"Error getting object {object_name} from bucket {self.bucket}: {e}")

        return content

    def get_s3_list_of_files(self, prefix, key=None):

        file_paths = []
        s3_folder = key
        # print("get_list_of_files : bucket_name: {} , key {} \n".format(self.s3_datalake_bucket, key))

        is_first = True
        ContinuationToken = ''

        while True:
            try:
                if is_first:
                    result = self.s3_client.list_objects_v2(Bucket=self.bucket,
                                                            Prefix=prefix)
                else:
                    result = self.s3_client.list_objects_v2(Bucket=self.bucket,
                                                            Prefix=prefix,
                                                            ContinuationToken=ContinuationToken)

                if 'Contents' in result:
                    sorted_result = sorted(result['Contents'],
                                           key=lambda k: k['LastModified'],
                                           reverse=False)  # reverse=True  , descending order

                    for _key in sorted_result:
                        if key is not None:
                            if key in _key['Key'] and _key['Key'][-1] != "/":
                                file_paths.append(_key['Key'])
                        else:
                            if _key['Key'][-1] != "/":
                                file_paths.append(_key['Key'])
                else:
                    break
            except KeyError:
                return
            except ClientError as e:
                if e.response['Error']['Code'] == "404":
                    logger.error("get_list_of_files : Code == 404 , error {}".format(e))
                    logger.error("get_list_of_files : bucket_name:{} , key {}".format(self.s3_datalake_bucket, key))

                else:
                    logger.error("get_list_of_files : error {}\n".format(e))
                    logger.error("get_list_of_files : bucket_name: {} , key {}\n".format(self.s3_datalake_bucket, key))
                return
            except Exception as e:
                logger.error(
                    "get_list_of_files : bucket_name: {} , key {} , error : {}\n".format(self.s3_datalake_bucket, key,
                                                                                         e))
                return

                # The S3 API is paginated, returning up to 1000 keys at a time.
                # Pass the continuation token into the next response, until we
                # reach the final page (when this field is missing).
            try:
                ContinuationToken = result['NextContinuationToken']
                is_first = False
            except KeyError:
                break

        return file_paths

    def save_json_to_s3(self, object_name: str, data: Dict[str, Any]) -> bool:
        """
        Save JSON data to an S3 bucket.

        Args:
            object_name: The name/path of the object in S3
            data: The dictionary data to save as JSON

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert dictionary to JSON string with proper encoding
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Encode the string to bytes using UTF-8
            json_bytes = json_str.encode('utf-8')
            
            # Upload the bytes directly to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_name,
                Body=json_bytes,
                ContentType='application/json'
            )
            logger.info(f"Successfully saved JSON to s3://{self.bucket}/{object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving JSON to s3://{self.bucket}/{object_name}: {e}")
            return False

