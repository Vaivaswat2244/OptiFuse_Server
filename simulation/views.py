import requests
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

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
    res.raise_for_status()  # This will raise an HTTPError for 4xx/5xx responses
    
    file_data = res.json()
    base64_content = file_data.get('content')
    if not base64_content:
        raise ValueError("File content from GitHub is empty.")

    try:
        # Robust decoding
        cleaned_content = base64_content.strip()
        padding = len(cleaned_content) % 4
        if padding > 0:
            cleaned_content += "=" * (4 - padding)
        return base64.b64decode(cleaned_content).decode('utf-8')
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        raise ValueError(f"Failed to decode file content: {e}")


# --- The Main API View ---

class LiveSimulationView(APIView):
    """
    An API endpoint to run a "live" optimization simulation. It fetches the
    application structure from a serverless.yml file in GitHub, enriches it
    with live performance data from AWS X-Ray, runs a suite of fusion
    algorithms, and returns the optimization results.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 1. Get request parameters and user profile
        repo_owner = request.data.get('owner')
        repo_name = request.data.get('repoName')
        
        if not repo_owner or not repo_name:
            return Response(
                {'error': 'owner and repoName are required in the request body.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        # 2. Check for necessary configurations
        if not profile.github_access_token:
            return Response({'error': 'GitHub token is not configured for this user.'}, status=status.HTTP_400_BAD_REQUEST)
        if not profile.aws_role_arn:
            return Response({'error': 'AWS Role ARN is not configured for this user.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 3. Fetch the serverless.yml from GitHub
            yaml_content = fetch_github_file(
                github_token=profile.github_access_token,
                owner=repo_owner,
                repo=repo_name,
                file_path='serverless.yml'
            )
            
            # 4. Build the base application model from the YAML file
            base_application = ApplicationBuilder.create_from_yaml_content(repo_name, yaml_content)

            # 5. Assume the user's AWS role
            aws_session = get_assumed_role_session(
                user_role_arn=profile.aws_role_arn,
                external_id=str(profile.aws_external_id)
            )

            # 6. Fetch live performance data from AWS
            live_metrics = fetch_live_xray_data(aws_session)
            
            # 7. Enrich the application model with the live data
            live_application = ApplicationBuilder.enrich_with_live_data(base_application, live_metrics)

            # 8. Run all simulation algorithms on the final, enriched model
            results = run_all_simulations(live_application)

            # 9. Clean results for JSON serialization before returning
            # (LambdaFunction objects cannot be directly converted to JSON)
            for result in results:
                if 'groups' in result and result['groups']:
                    result['groups'] = [[func.id for func in group] for group in result['groups']]

            return Response(results, status=status.HTTP_200_OK)

        except requests.exceptions.HTTPError as e:
            # Handle errors from the GitHub API call
            status_code = e.response.status_code
            if status_code == 404:
                error_message = "serverless.yml not found in the specified repository."
            else:
                error_message = "Failed to fetch file from GitHub."
            return Response({'error': error_message, 'details': e.response.text}, status=status_code)
        
        except ValueError as e:
            # Handle errors from our own logic (e.g., bad YAML, decoding errors)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e: 
            return Response(
                {'error': 'An unexpected error occurred during the live analysis.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )