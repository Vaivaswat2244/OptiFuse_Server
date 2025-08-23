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
        
    )
    print("--- logs begin  of trace summaries---")    
    print(trace_summaries)

    function_metrics = {}

    paginator = xray_client.get_paginator('get_trace_summaries')
    page_iterator = paginator.paginate(
        StartTime=start_time,
        EndTime=end_time,
        
    )
    print("--- logs begin of page_iterator---")
    print(page_iterator)

    for page in page_iterator:
        print(f"--- Found a page with {len(page.get('TraceSummaries', []))} summaries ---")
        for summary in page.get('TraceSummaries', []):
            # The filter ensures that the Annotations dictionary and the specific key will be present.
            # We add checks for safety anyway.
            annotations = summary.get('Annotations', {})
            if 'aws.lambda.function_name' in annotations:
                
                # The function name is an array of strings in the annotations
                # We take the first one as it represents the entry point of the trace.
                function_name = annotations['aws.lambda.function_name'][0]
                
                # Initialize the dictionary for this function if it's the first time we see it
                if function_name not in function_metrics:
                    function_metrics[function_name] = {
                        'total_duration': 0.0,
                        'invocations': 0
                    }
                
                # Add the duration of this trace to the function's total
                function_metrics[function_name]['total_duration'] += summary.get('Duration', 0.0)
                # Increment the invocation count
                function_metrics[function_name]['invocations'] += 1

    # for summary in trace_summaries.get('TraceSummaries', []):
    #     if summary.get('ResourceARNs'):
    #         function_arn = summary['ResourceARNs'][0]['ARN']
    #         function_name = function_arn.split(':')[-1]
            
    #         if function_name not in function_metrics:
    #             function_metrics[function_name] = {'total_duration': 0, 'invocations': 0}
            
    #         function_metrics[function_name]['total_duration'] += summary.get('Duration', 0)
    #         function_metrics[function_name]['invocations'] += 1

    processed_spec = {}
    for name, metrics in function_metrics.items():
        if metrics['invocations'] > 0:
            avg_duration_ms = (metrics['total_duration'] / metrics['invocations']) * 1000
            processed_spec[name] = {
                'avg_runtime_ms': round(avg_duration_ms),
                'avg_memory_mb': 256, 
            }
    return processed_spec