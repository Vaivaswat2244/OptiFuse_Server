import boto3
import time
from typing import Dict, Any, List
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

def fetch_live_xray_data(aws_session, service_name: str, stage: str, function_ids: List[str]) -> Dict[str, Any]:
    """
    Fetches live performance data using CloudWatch Logs Insights.
    This version includes extensive logging and more robust error handling.
    """
    logs_client = aws_session.client('logs')
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    # Construct the full log group names
    log_group_names = [f"/aws/lambda/{service_name}-{stage}-{name}" for name in function_ids]

    if not log_group_names:
        print("LOG: No function names provided, cannot query CloudWatch.")
        return {}

    print(f"LOG: Attempting to query {len(log_group_names)} log groups: {log_group_names}")

    query = """
    filter @type = "REPORT"
    | stats avg(@duration) as avgDurationMS, 
            avg(@maxMemoryUsed) / 1024 / 1024 as avgMemoryMB,
            count(*) as invocations
    by @log as logGroupName 
    """

    try:
        start_query_response = logs_client.start_query(
            logGroupNames=log_group_names,
            startTime=int(start_time.timestamp()),
            endTime=int(end_time.timestamp()),
            queryString=query,
            limit=10000
        )
        query_id = start_query_response['queryId']
        print(f"LOG: CloudWatch query started with ID: {query_id}")
    except logs_client.exceptions.ResourceNotFoundException as e:
        print(f"ERROR: One or more log groups not found. Aborting. Details: {e}")
        return {} # Gracefully exit if no logs exist
    except Exception as e:
        print(f"ERROR: Failed to start CloudWatch query. Details: {e}")
        raise # Re-raise the exception to be caught by the view

    # Poll for the query to complete
    response = None
    max_wait_seconds = 60
    wait_time = 0
    while wait_time < max_wait_seconds:
        print(f"LOG: Checking query status... (Attempt {wait_time + 1})")
        response = logs_client.get_query_results(queryId=query_id)
        if response['status'] in ['Complete', 'Failed', 'Cancelled']:
            print(f"LOG: Query finished with status: {response['status']}")
            break
        time.sleep(1)
        wait_time += 1
    
    # --- ADDED DEFENSIVE CHECKS ---
    if not response:
        print("ERROR: Query response was None after waiting.")
        return {}

    if response['status'] != 'Complete':
        print(f"ERROR: CloudWatch query did not complete successfully. Final status: {response['status']}")
        return {}

    print(f"LOG: Query complete. Found {len(response.get('results', []))} result rows.")

    # Process the results
    processed_spec = {}
    
    # This is the line that was likely failing. We now protect it.
    query_results = response.get('results', [])
    if not query_results:
        print("LOG: Query was successful but returned no result rows.")
        return {}

    for result in query_results:
        log_stream_field = next((field['value'] for field in result if field['field'] == 'logStreamName'), None)
        if not log_stream_field:
            continue
            
        matched_function_id = None
        for func_id in function_ids:
            if f"-{func_id}" in log_stream_field:
                matched_function_id = func_id
                break
        
        if matched_function_id:
            try:
                avg_duration = float(next(field['value'] for field in result if field['field'] == 'avgDurationMS'))
                avg_memory = float(next(field['value'] for field in result if field['field'] == 'avgMemoryMB'))

                processed_spec[matched_function_id] = {
                    'avg_runtime_ms': round(avg_duration),
                    'avg_memory_mb': round(avg_memory),
                }
            except (StopIteration, TypeError, ValueError) as e:
                print(f"WARNING: Could not parse result row. Skipping. Row: {result}, Error: {e}")

    print("--- Processed Live Metrics from CloudWatch ---")
    print(processed_spec)
    print("---------------------------------------------")
            
    return processed_spec