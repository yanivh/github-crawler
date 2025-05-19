import os
import sys
from datetime import date, timedelta, datetime
from types import SimpleNamespace
from awsglue.utils import getResolvedOptions

def load_glue_context(start_date: str = None, end_date: str = None) -> SimpleNamespace:
    """

    Args:
        start_date: The start date for the job.
        end_date: The end date for the job.

    Returns:
        A namespace object containing the job context.
    """

    args = getResolvedOptions(sys.argv,
                              ['start_date',
                                'end_date',
                                'github_token_secret_name',
                                'default_s3_bucket',
                                'owner',
                                'repo',
                                'environment'])

    if args['start_date'] == 'Yesterday':
        yesterday = datetime.today() - timedelta(days=1)
        args['start_date'] = yesterday.strftime('%Y-%m-%d')

    if args['end_date'] == 'Today':
        args['end_date'] = datetime.today().strftime('%Y-%m-%d')

    print(f"start_date:{args['start_date']},end_date:{args['end_date']}'")

    return args
