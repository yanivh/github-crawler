import logging
import os
import sys
from datetime import date, timedelta, datetime
from types import SimpleNamespace
import json
import boto3
from botocore.exceptions import ClientError
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
import pandas as pd
from dateutil import rrule
import logging
# from src.b2b_utils.athena_toolkit import athena_data_type_mapping


logger = logging.getLogger("b2b-data")
logger.setLevel(logging.INFO)
logger.debug("main message")
# boto3.set_stream_logger('', logging.DEBUG)

def load_glue_contex():
    if "GLUE_PYTHON_VERSION" in os.environ:
        from awsglue.utils import getResolvedOptions

        args = getResolvedOptions(sys.argv, ["start_date",
                                             "end_date",
                                             "environment",
                                             "s3_datalake_bucket",
                                             "artifact_sha",
                                             "s3_artifact_bucket",
                                             "s3_artifact_prefix"])

        if args['start_date'] == 'Yesterday':
            yesterday = datetime.today() - timedelta(days=1)
            args['start_date'] = yesterday.strftime('%Y-%m-%d')

        if args['end_date'] == 'Today':
            args['end_date'] = datetime.today().strftime('%Y-%m-%d')

        # TO ADD CUSTOM DATES
        # args['start_date'] = date(2024, 11, 19).strftime('%Y-%m-%d')
        # args['end_date'] = date(2024, 11, 23).strftime('%Y-%m-%d')

        print(f"start_date:{args['start_date']},end_date:{args['end_date']}'")

    else:  # support Local debugging

        # set specific date
        start_date = date(2017, 11, 30)
        end_date = date(2022, 6, 1)

        environment = 'production'  # 'production' / 'sandbox' staging
        s3_datalake_bucket = 'babbel-b2b-reports-data-production' #'babbel-b2b-data-datalake-1'
        artifact_sha = 'FDGJS35HK8036MV'
        s3_artifact_bucket = 'babbel-b2b-data-datalake-1'
        s3_datalake_prefix = ''


        args = {
            "start_date": f"{str(start_date)}",
            "end_date": f"{str(end_date)}",
            "environment": f'{environment}',
            "s3_datalake_bucket": f"{str(s3_datalake_bucket)}",
            "artifact_sha": f'{artifact_sha}',
            "s3_artifact_bucket": f'{s3_artifact_bucket}',
            "s3_artifact_prefix": f'{s3_datalake_prefix}'
        }

    return SimpleNamespace(**args)


class ActivitiesLoader:
    def __init__(self,
                 start_date: str,
                 end_date: str,
                 environment: str,
                 s3_datalake_bucket: str,
                 artifact_sha: str, s3_artifact_bucket: str,
                 s3_artifact_prefix: str
                 ):
        self.s3_artifact_bucket = s3_artifact_bucket
        self.s3_artifact_prefix = s3_artifact_prefix
        self.artifact_sha = artifact_sha
        self.s3_datalake_bucket = s3_datalake_bucket
        self.environment = environment
        self.start_date = start_date
        self.end_date = end_date

        self.activities_raw_data = []

        self.s3_client = boto3.client("s3")
        self.s3_resource = boto3.resource('s3')

        self.model_info = self.get_model_info()
        print (1)

    def process_raw_activities_data(self, start_date: date, end_date: date):
        '''
        get all Activities data per range (S3/RAW), enrich, apply schema, save as parquet.
        :param : start_date
        :param : end_date
        :return:
        '''

        dates = self.get_date_range('DAILY', start_date, end_date)
        date_len = len(dates)

        print(f'get_activities_data:start_date:{start_date}:end_date:{end_date}')
        print(f' {date_len} Dates to process')

        current = 0
        for _date in dates:
            self.process_activities_data_per_date(_date)
            current = current + 1
            print(f'complete process {current} from:{date_len} - Current date {_date}')

    # @staticmethod
    def process_activities_data_per_date(self, date):
        '''
        get all records per specific date , include many orgs
        enrich with dates
        save to  S3 as Parquet (include Schema validation)
        :param start_date:
        :param end_date:
        :return:
        '''

        # print(f'{date}')

        date_ = date.strftime('%Y-%m-%d')

        files_to_process = self.get_s3_list_of_files(date_)

        if files_to_process:
            print(f'files_to_process {len(files_to_process)}  - Current date {date_}')
            for file in files_to_process:

                df = pd.DataFrame()
                df = pd.read_csv(f"s3://{self.s3_datalake_bucket}/{file}", parse_dates=['DATE'])

                if not df.empty:
                    df = df.reset_index(drop=True)
                    df_enriched = self.enrich(df)
                    self.save_activities_data(df_enriched, file, date_)

    def enrich(self, df):
        '''
        add week/month/quarter parts .
        :param df:
        :return:
        '''

        df['week'] = df['DATE'].dt.isocalendar().week
        df['day_of_week'] = df['DATE'].dt.dayofweek
        df['day_in_month'] = df['DATE'].dt.days_in_month
        df['quarter'] = df['DATE'].dt.quarter
        # print(df)

        return df

    def get_s3_list_of_files(self, key):

        file_paths = []
        s3_folder = key
        # print("get_list_of_files : bucket_name: {} , key {} \n".format(self.s3_datalake_bucket, key))

        is_first = True
        ContinuationToken = ''

        while True:
            try:
                if is_first:
                    result = self.s3_client.list_objects_v2(Bucket=self.s3_datalake_bucket,
                                                            Prefix=self.model_info["s3_datalake_raw_folder"])
                else:
                    result = self.s3_client.list_objects_v2(Bucket=self.s3_datalake_bucket,
                                                            Prefix=self.model_info["s3_datalake_raw_folder"],
                                                            ContinuationToken=ContinuationToken)

                if 'Contents' in result:
                    sorted_result = sorted(result['Contents'],
                                           key=lambda k: k['LastModified'],
                                           reverse=False)  # reverse=True  , descending order

                    for _key in sorted_result:
                        if key in _key['Key']:
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
                    "get_list_of_files : bucket_name: {} , key {} , error : {}\n".format(self.s3_datalake_bucket, key, e))
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

    def validate_schema(self, df):
        '''
        # TODO: try to convert cast(pa.float32()) - DONE
        # TODO: enforce naming like json file
        # TODO: check for new / missing  columns and alert
        '''

        columns = self.model_info['schema']

        for column in columns:
            if column in df:
                _type = self.athena_data_type_mapping(columns[column]['type'])
                df[column] = df[column].astype(_type)

        table = pa.Table.from_pandas(df)

        return pa.Table.from_arrays(table.columns, table.column_names)

    def athena_data_type_mapping(self, athena_type):
        _type = ''

        if athena_type.lower() == 'VARCHAR'.lower():
            _type = 'str'.lower()
        if athena_type.lower() == 'STRING'.lower():
            _type = 'str'.lower()
        if athena_type.lower() == 'bigint'.lower():
            _type = 'int'.lower()
        if athena_type.lower() == 'BOOLEAN'.lower():
            _type = 'bool'.lower()
        if athena_type.lower() == 'double'.lower():
            _type = 'float64'.lower()
        if athena_type.lower() == 'timestamp'.lower():
            _type = 'datetime64'.lower()
        return _type

    def get_model_info(self):

        if "GLUE_PYTHON_VERSION" in os.environ:
            model_path = f"{self.s3_artifact_prefix}etl-artifacts/models/info/learning_activities.json"
            obj = self.s3_resource.Object(self.s3_artifact_bucket, model_path)
            content = obj.get()['Body'].read()
        else:
            # model_path = f"{self.s3_artifact_prefix}etl-artifacts/models/info/learning_activities.json"
            # obj = self.s3_resource.Object(self.s3_artifact_bucket, model_path)
            # content = obj.get()['Body'].read()

            # # support work locally
            with open(os.path.expanduser("../models/info/learning_activities.json")) as key:
                content = key.read()

        fields_dict = json.loads(content)
        model_info = fields_dict[0]

        return model_info

    def save_activities_data(self, df, key, date):

        file_type = "parquet"

        date_ = datetime.strptime(date, '%Y-%m-%d').date()

        _table = self.validate_schema(df)
        _buffer = BytesIO()
        pq.write_table(_table, _buffer)

        slug = self.extract_org_name(key)

        file_name = f'{"processed"}_activities_' \
                    f'{slug}_' \
                    f'{date}.{file_type}'

        key = f'{self.model_info["s3_datalake_processed_folder"]}/' \
              f'org={slug}/' \
              f'year={date_.year}/' \
              f'month={date_.month}/' \
              f'day={date_.day}/{file_name}'

        self.s3_resource.Object(self.s3_datalake_bucket, f'{key}').put(Body=_buffer.getvalue())

        return file_name

    def extract_org_name(self, key):
        '''
        extract slug (org) name from s3 key name
        :param key:
        :return:
        '''

        import re

        regex = r"org=(.*?)\/year"

        test_str = key
        matches = re.finditer(regex, test_str)

        for matchNum, match in enumerate(matches, start=1):

            # print("Match {matchNum} was found at {start}-{end}: {match}".format(matchNum=matchNum, start=match.start(),
            #                                                                     end=match.end(), match=match.group()))

            for groupNum in range(0, len(match.groups())):
                groupNum = groupNum + 1

                # print("Group {groupNum} found at {start}-{end}: {group}".format(groupNum=groupNum,
                #                                                                 start=match.start(groupNum),
                #                                                                 end=match.end(groupNum),
                #                                                                 group=match.group(groupNum)))

        slug = match.groups()[0]

        return slug

    def get_date_range(self, granularity, start_date, end_date):
        '''
            granularty =  HOURLY / DAILY
            :param granularty:
            :param start_date:
            :param end_date:
            :return:
            '''

        if granularity == 'DAILY':
            i = rrule.DAILY
        elif granularity == 'HOURLY':
            i = rrule.HOURLY
        # TODO improve here

        # convert string date , ddate objects
        start_date_ = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_ = datetime.strptime(end_date, '%Y-%m-%d').date()

        dates = list(rrule.rrule(i, dtstart=start_date_, until=end_date_))

        return dates


if __name__ == "__main__":
    args = load_glue_contex()

    activities_loader = ActivitiesLoader(
        start_date=args.start_date,
        end_date=args.end_date,
        environment=args.environment,
        s3_datalake_bucket=args.s3_datalake_bucket,
        artifact_sha=args.artifact_sha,
        s3_artifact_bucket=args.s3_artifact_bucket,
        s3_artifact_prefix=args.s3_artifact_prefix
    )

    activities_loader.process_raw_activities_data(start_date=args.start_date,
                                                  end_date=args.end_date)
