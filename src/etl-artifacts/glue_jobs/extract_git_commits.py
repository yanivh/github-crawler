import hashlib
import logging
import os
import sys
from datetime import date, timedelta, datetime
from types import SimpleNamespace
import json
import snowflake.connector
import boto3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from io import StringIO
import pyarrow as pa
import pandas as pd
import logging

logger = logging.getLogger("b2b-data")
logger.setLevel(logging.INFO)
logger.debug("main message")
# boto3.set_stream_logger('', logging.DEBUG)


def load_glue_contex():
    if "GLUE_PYTHON_VERSION" in os.environ:
        from awsglue.utils import getResolvedOptions

        args = getResolvedOptions(sys.argv,
                                  ["start_date", "end_date",
                                   "environment",
                                   "s3_datalake_bucket",
                                   "artifact_sha",
                                   "snowflake_private_key_secret_name",
                                   "snowflake_user_account_secret_name",
                                   "s3_artifact_bucket",
                                   "s3_artifact_prefix"])

        if args['start_date'] == 'Yesterday':
            yesterday = datetime.today() - timedelta(days=1)
            args['start_date'] = yesterday.strftime('%Y-%m-%d')

        if args['end_date'] == 'Today':
            args['end_date'] = datetime.today().strftime('%Y-%m-%d')

        #TO ADD CUSTOM DATES
        # args['start_date'] = date(2024, 11, 19).strftime('%Y-%m-%d')
        # args['end_date'] = date(2024, 11, 23).strftime('%Y-%m-%d')

        print(f"start_date:{args['start_date']},end_date:{args['end_date']}'")

    else:  # support Local debugging

        end_date = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')

        environment = 'sandbox'  # 'production' / 'sandbox'
        snowflake_private_key_secret_name = 'b2b-data_yaniv_snowflake_private_key'
        snowflake_user_account_secret_name = "b2b-data_snowflake_user_account_secret_name"
        s3_datalake_bucket = 'babbel-b2b-data-datalake-1'
        artifact_sha = 'FDGJS35HK8036MV'
        s3_artifact_bucket = 'babbel-b2b-data-datalake-1'
        s3_artifact_prefix = 'learning-activities/FDGJS35HK8036MV/'

        args = {
            "start_date": f"{str(start_date)}",
            "end_date": f"{str(end_date)}",
            "environment": f'{environment}',
            "s3_datalake_bucket": f'{s3_datalake_bucket}',
            "artifact_sha": artifact_sha,
            "snowflake_private_key_secret_name": f'{snowflake_private_key_secret_name}',
            "snowflake_user_account_secret_name": f'{snowflake_user_account_secret_name}',
            "s3_artifact_bucket": f'{s3_artifact_bucket}',
            "s3_artifact_prefix": f'{s3_artifact_prefix}'
        }

    return SimpleNamespace(**args)


class Snowflake:
    """This class provides a wrapper around Snowflake which is used for fetch data."""

    # TODO : connection to None outside of the class, and use a singleton pattern to ensure that only one connection is created.
    def __init__(self,
                 s3_object,
                 snowflake_private_key_secret_name,
                 snowflake_user_account_secret_name):

        self.secrets_client = boto3.client("secretsmanager")
        self.s3_object = s3_object

        # read from secrets manager
        snowflake_user_account = self.get_secret(snowflake_user_account_secret_name)
        user_account_info = json.loads(snowflake_user_account['SecretString'])

        self.user = user_account_info['user']
        self.account_identifier = user_account_info['account']
        self.warehouse = user_account_info['warehouse']
        self.hades_database = user_account_info['hades_database']
        self.hades_schema = user_account_info['hades_schema']

        self.dpe_database = user_account_info['dpe_database']
        self.ldm_database = user_account_info['ldm_database']
        self.dpe_schema = "LEARNER_MINUTES"

        self.connection = None
        self.snowflake_private_key_secret_name = snowflake_private_key_secret_name

        if self.connection is None:  # TODO : improve and use singleton
            self.connection = self.connect()

    def get_secret(self, secret_name):
        '''

        :param secret_name:
        :return:
        '''

        logger.info(f"Secret is: {secret_name}")

        secret = self.secrets_client.get_secret_value(SecretId=secret_name)

        return secret

    def get_rsa_key(self):
        '''

        :param key_name:
        :return:
        '''

        private_key = self.get_secret(self.snowflake_private_key_secret_name)

        p_key = serialization.load_pem_private_key(
            bytes(private_key['SecretString'], "utf-8"),
            password=None,
            backend=default_backend()
        )

        pkb = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pkb

    def connect(self, key_name='rsa_key.p8'):
        '''

        :param key_name:
        :return:
        '''

        pkb = self.get_rsa_key()

        conn = snowflake.connector.connect(user=self.user,
                                           account=self.account_identifier,
                                           private_key=pkb,
                                           warehouse=self.warehouse,
                                           database=self.dpe_database,
                                           schema=self.dpe_schema)

        return conn

    def query_fetch(self, query):
        '''

        :param con:
        :param query:
        :return: panda dataframe
        '''

        df = pd.DataFrame()
        try:
            df = self.connection.cursor().execute(query).fetch_pandas_all()
            if df.empty:
                print(f'dataframe empty')
        except Exception as ex:
            print(ex)
        # finally:
        # con.close()
        return df


class ActivitiesLoader:
    def __init__(self,
                 start_date: str,
                 end_date: str,
                 environment: str,
                 s3_datalake_bucket: str,
                 artifact_sha: str,
                 snowflake_private_key_secret_name: str,
                 snowflake_user_account_secret_name: str,
                 s3_artifact_bucket: str,
                 s3_artifact_prefix: str
                 ):
        self.s3_artifact_bucket = s3_artifact_bucket
        self.s3_artifact_prefix = s3_artifact_prefix
        self.artifact_sha = artifact_sha
        self.s3_datalake_bucket = s3_datalake_bucket
        self.environment = environment
        self.start_date = start_date
        self.end_date = end_date
        self.snowflake_private_key_secret_name = snowflake_private_key_secret_name
        self.snowflake_user_account_secret_name = snowflake_user_account_secret_name

        self.activities_raw_data = []

        self.s3_client = boto3.client("s3")
        self.s3_resource = boto3.resource('s3')

        self.model_info = self.get_model_info(self)

        self.secrets_client = boto3.client("secretsmanager")

        self.snowflake = Snowflake(self.s3_client, self.snowflake_private_key_secret_name,
                                   self.snowflake_user_account_secret_name)

    def get_aws_secret(self, secret_name):
        '''

        :param secret_name:
        :return:
        '''

        logger.info(f"Secret is: {secret_name}")

        secret = self.secrets_client.get_secret_value(SecretId=secret_name)

        return secret

    def get_activities_data(self, start_date: date, end_date: date):
        '''
        get all Activities data per specific date
        using table :
            LDM_PRODUCTION.LEARNER_MINUTES.DAILY_USER_LM
        :param : start_date
        :param : end_date
        :return:
        '''

        print(f'get_activities_data:start_date:{start_date}:end_date:{end_date}\n')

        self.get_activities_data_per_date(self, start_date, end_date)

    # @staticmethod
    def get_activities_data_per_date(self, start_date, end_date):
        '''

        :param start_date:
        :param end_date:
        :return:
        '''

        result = pd.DataFrame()

        print(f"start_date:{start_date}, end_date:{end_date}\n")
        sql = self.get_query(start_date, end_date)
        result = self.snowflake.query_fetch(sql)

        # print(result)
        if not result.empty:
            if self.environment == 'sandbox':  # replace PII data (UUID , email, IP, etc.)
                result['UUID'] = result['UUID'].apply(lambda x: self.sha256(x))

        return result

    def validate_schema(self, df):
        '''

        :param df:
        :return:
        '''

        df = df.reset_index(drop=True)
        table = pa.Table.from_pandas(df)

        columns = self.model_info['schema']

        # TODO refactor
        for c in table.schema:
            if c.name in columns:
                if c.type == columns[c.name]['type']:
                    print(f'match type {c.name} , Type {c.type}\n')
                else:
                    print(f'error : {c.name} is not in the expected Type\n')
            #       TODO: try to convert cast(pa.float32())
            else:
                print(f'error : {c.name} is not define\n')

        return pa.Table.from_arrays(table.columns, table.column_names)

    def sha256(self, text):
        sha = hashlib.sha256()
        sha.update(text.encode('utf-8'))
        return sha.hexdigest()

    @staticmethod
    def get_model_info(self):

        if "GLUE_PYTHON_VERSION" in os.environ:
            model_path = f"{self.s3_artifact_prefix}etl-artifacts/models/info/learning_activities.json"
            logger.info(f'model_path: {model_path}')
            obj = self.s3_resource.Object(self.s3_artifact_bucket, model_path)
            content = obj.get()['Body'].read()

        else:  # support work locally
            model_path = f"{self.s3_artifact_prefix}etl-artifacts/models/info/learning_activities.json"
            logger.info(f'model_path: {model_path}')
            obj = self.s3_resource.Object(self.s3_artifact_bucket, model_path)
            content = obj.get()['Body'].read()

            # with open(os.path.expanduser("../models/info/learning_activities.json")) as key:
            #     content = key.read()

        fields_dict = json.loads(content)
        model_info = fields_dict[0]

        return model_info

    def get_query(self, start_date, end_date):
        '''

        '''

        print(f"start_date:{start_date}, end_date:{end_date}\n")

        if "GLUE_PYTHON_VERSION" in os.environ:
            path = f"{self.s3_artifact_prefix}etl-artifacts/Sql/DDM/{self.model_info['extract_query']}"
            logger.info(path)
            logger.info(path)
            obj = self.s3_resource.Object(self.s3_artifact_bucket, path)
            sql = obj.get()['Body'].read()
            sql = sql.decode('utf-8')
        else:
            ## support work locally
            self.model_info['extract_query']
            with open(os.path.expanduser(f"../sql/ddm/{self.model_info['extract_query']}")) as key:
                sql = key.read()

            print(f"pre sql{sql}\n")

        source_table = f'{self.snowflake.ldm_database}.{self.model_info["source_table"]}'
        source_table_membership = f'{self.snowflake.hades_database}.{self.model_info["source_table_membership"]}'

        sql = sql.replace('%source_table%', source_table).replace('%source_table_membership%', source_table_membership)


        sql = \
            sql.replace('%start_date%', start_date). \
                replace('%end_date%', end_date). \
                replace('%ignor_orgs%', self.model_info["ignor_orgs"])

        print(f"post sql{sql}\n")

        return sql

    def save_activities_per_day(self, group_slug, group_date):

        layer = 'raw'
        file_type = "csv"

        csv_buffer = StringIO()
        group_date[1].to_csv(csv_buffer, index=False)

        try:
            file_name = f'{layer}_activities_{group_slug[0]}_{group_date[0]}.{file_type}'

            key = f'{self.model_info["s3_datalake_raw_folder"]}/' \
                  f'org={group_slug[0]}/' \
                  f'year={group_date[0].year}/' \
                  f'month={group_date[0].month}/' \
                  f'day={group_date[0].day}/{file_name}'
            self.s3_resource.Object(self.s3_datalake_bucket, f'{key}').put(Body=csv_buffer.getvalue())

        except Exception as ex:
            print(ex)

        return file_name

    def save_activities_data(self, activities_df):
        '''

        :param layer:
        :param df:
        :return:
        '''

        # TODO : replace for loop with df df.apply function
        #       check AWS Glue for Ray, support scaling pandas.
        if len(activities_df) > 0:
            groups_slug_orgs = activities_df.groupby('SLUG')
            for group_slug_org in groups_slug_orgs:
                print(f'slug : {group_slug_org[0]}\n')
                groups_date = group_slug_org[1].groupby('DATE')
                for group_date in groups_date:
                    print(f'date : {group_date[0]} - slug : {group_slug_org[0]}\n')

                    file_name = self.save_activities_per_day(group_slug_org, group_date)
        else:
            print(f"NO Data to process for ")

        return file_name


if __name__ == "__main__":
    args = load_glue_contex()

    activities_df = pd.DataFrame()

    activities_loader = ActivitiesLoader(
        start_date=args.start_date,
        end_date=args.end_date,
        environment=args.environment,
        s3_datalake_bucket=args.s3_datalake_bucket,
        artifact_sha=args.artifact_sha,
        snowflake_private_key_secret_name=args.snowflake_private_key_secret_name,
        snowflake_user_account_secret_name=args.snowflake_user_account_secret_name,
        s3_artifact_bucket=args.s3_artifact_bucket,
        s3_artifact_prefix=args.s3_artifact_prefix
    )

    def load_activities():

        activities = pd.DataFrame()
        activities = activities_loader.get_activities_data_per_date(start_date=args.start_date, end_date=args.end_date)

        return activities


    activities_df = load_activities()

    if not activities_df.empty:
        activities_loader.save_activities_data(activities_df)
    else:
        if args.environment == 'production':
            raise Exception(f'dataset is missing for date: {args.start_date}')

