import boto3
from datetime import datetime, timedelta, timezone

def get_assumed_role_session(user_role_arn: str, external_id: str):
    """
    Assumes the user's IAM role and returns a temporary boto3 session.
    """
    sts_client = boto3.client('sts')
    
    assumed_role_object = sts_client.assume_role(
        RoleArn=user_role_arn,
        RoleSessionName="OptifuseAnalysisSession",
        ExternalId=external_id
    )
    
    credentials = assumed_role_object['Credentials']
    
    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
    )

def fetch_live_xray_data(aws_session, time_window_hours: int = 24) -> dict:
    """
    Fetches and processes X-Ray trace data for a given time window.
    Returns a simplified dictionary of function names to their average runtime.
    """
    xray_client = aws_session.client('xray')
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=time_window_hours)

    # This is a simplified placeholder for the complex task of trace analysis.
    # In a real app, you would paginate and process full traces.
    trace_summaries = xray_client.get_trace_summaries(
        StartTime=start_time,
        EndTime=end_time,
        FilterExpression='service.type = "AWS::Lambda"'
    )

    function_metrics = {}
    for summary in trace_summaries.get('TraceSummaries', []):
        if summary.get('ResourceARNs'):
            function_arn = summary['ResourceARNs'][0]['ARN']
            function_name = function_arn.split(':')[-1]
            
            if function_name not in function_metrics:
                function_metrics[function_name] = {'total_duration': 0, 'invocations': 0}
            
            function_metrics[function_name]['total_duration'] += summary.get('Duration', 0)
            function_metrics[function_name]['invocations'] += 1

    processed_spec = {}
    for name, metrics in function_metrics.items():
        if metrics['invocations'] > 0:
            avg_duration_ms = (metrics['total_duration'] / metrics['invocations']) * 1000
            processed_spec[name] = {
                'avg_runtime_ms': round(avg_duration_ms),
                'avg_memory_mb': 256, 
            }
    return processed_spec