import requests
import base64
import yaml
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from botocore.exceptions import ClientError

from core.models import Profile
from .core.builder import ApplicationBuilder
from .connectors.aws import get_assumed_role_session, fetch_live_xray_data
from .runner import run_all_simulations

def fetch_github_file(github_token: str, owner: str, repo: str, file_path: str) -> str:
    """
    Fetches the content of a specific file from a GitHub repository.
    Raises an exception if the file cannot be fetched or decoded.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    
    res = requests.get(api_url, headers=headers)
    res.raise_for_status() # Raises HTTPError for 4xx/5xx responses
    
    file_data = res.json()
    base64_content = file_data.get('content')
    if not base64_content:
        raise ValueError("File content from GitHub is empty.")

    try:
        cleaned_content = base64_content.strip()
        padding = len(cleaned_content) % 4
        if padding > 0:
            cleaned_content += "=" * (4 - padding)
        return base64.b64decode(cleaned_content).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to decode file content: {e}")

class LiveSimulationView(APIView):
    """
    Orchestrates the live optimization workflow using the CloudWatch-First strategy.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        repo_owner = request.data.get('owner')
        repo_name = request.data.get('repoName')
        
        if not repo_owner or not repo_name:
            return Response({'error': 'owner and repoName are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not profile.github_access_token or not profile.aws_role_arn:
            return Response({'error': 'GitHub token and AWS Role ARN must be configured.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Step 1: Fetch the serverless.yml from GitHub
            print("Step 1/7: Fetching serverless.yml from GitHub...")
            yaml_content = fetch_github_file(
                github_token=profile.github_access_token,
                owner=repo_owner,
                repo=repo_name,
                file_path='serverless.yml'
            )
            
            # Step 2: Build the base application model from the YAML file
            print("Step 2/7: Parsing YAML and building base application model...")
            base_application = ApplicationBuilder.create_from_yaml_content(repo_name, yaml_content)

            # Step 3: Extract function names needed for the CloudWatch query
            print("Step 3/7: Extracting function names for AWS query...")
            function_ids = [func.id for func in base_application.functions]
            
            # --- NEW STEP: Extract service and stage from YAML ---
            print("Step 4/7: Extracting service and stage from YAML...")
            try:
                yml_spec = yaml.safe_load(yaml_content)
                service_name = yml_spec.get('service', 'unknown-service')
                stage = yml_spec.get('provider', {}).get('stage', 'dev')
            except (yaml.YAMLError, AttributeError):
                raise ValueError("Could not parse service name or stage from serverless.yml.")
            # --- END OF NEW STEP ---

            # Step 5: Assume the user's AWS role
            print("Step 5/7: Assuming user's AWS IAM Role...")
            aws_session = get_assumed_role_session(
                user_role_arn=profile.aws_role_arn,
                external_id=str(profile.aws_external_id)
            )

            # Step 6: Fetch live performance data from AWS
            print("Step 6/7: Fetching live performance data from CloudWatch Logs...")
            live_metrics = fetch_live_xray_data(aws_session, service_name, stage, function_ids)
            
            # Step 7: Enrich the application model with the live data
            print("Step 7/7: Enriching application model with live data...")
            live_application = ApplicationBuilder.enrich_with_live_data(base_application, live_metrics)

            # Run the final simulation
            print("Running simulations...")
            results = run_all_simulations(live_application)

            # Clean results for JSON serialization
            for result in results:
                if 'groups' in result and result.get('groups'):
                    result['groups'] = [[func.id for func in group] for group in result['groups']]

            return Response(results, status=status.HTTP_200_OK)

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 500
            if status_code == 404:
                error_message = "serverless.yml not found in the specified repository."
            else:
                error_message = "Failed to fetch file from GitHub."
            return Response({'error': error_message, 'details': e.response.text}, status=status_code)
        
        except ValueError as e:
            # Catches errors from our builder/parser logic
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        except ClientError as e:
            # Catches specific AWS/boto3 errors
            error_response = e.response
            error_code = error_response.get('Error', {}).get('Code', 'Unknown')
            error_message = error_response.get('Error', {}).get('Message', 'No details from AWS.')
            return Response({
                'error': 'An error occurred while communicating with AWS.',
                'details': f"{error_code}: {error_message}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            # A final catch-all for any other unexpected errors
            print(f"UNEXPECTED ERROR: {e}") # Log the full error for debugging
            return Response(
                {'error': 'An unexpected internal server error occurred.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )