from decouple import config
import requests
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny      # <-- NEW IMPORT
from rest_framework.authtoken.models import Token     # <-- NEW IMPORT
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth.models import User
from .models import Profile

class GitHubLogin(APIView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'No code provided'}, status=status.HTTP_400_BAD_REQUEST)

        token_params = {
            'client_id': config('GITHUB_CLIENT_ID'),
            'client_secret': config('GITHUB_CLIENT_SECRET'),
            'code': code,
        }
        token_headers = {'Accept': 'application/json'}
        token_res = requests.post('https://github.com/login/oauth/access_token', params=token_params, headers=token_headers)
        token_data = token_res.json()
        print("--- GitHub Token Response ---")
        print(token_data)
        access_token = token_data.get('access_token')

        if not access_token:
            return Response({'error': 'Could not retrieve access token'}, status=status.HTTP_400_BAD_REQUEST)

        user_headers = {'Authorization': f'token {access_token}', 'Accept': 'application/vnd.github.v3+json'}
        user_res = requests.get('https://api.github.com/user', headers=user_headers)
        user_data = user_res.json()

        username = user_data.get('login')
        if not username:
            return Response({'error': 'Could not retrieve username from GitHub.'}, status=status.HTTP_400_BAD_REQUEST)
        user, created = User.objects.get_or_create(username=username)

        if created:
            user.email = user_data.get('email')
            user.set_unusable_password()
            user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.github_access_token = access_token
        profile.save()

        token_obj, created = Token.objects.get_or_create(user=user)
        # print("this is the token", optifuse_token)

        response_data = {
            'token': token_obj.key,
            'username': user.username,
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

class RepositoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        try:
            github_token = user.profile.github_access_token
            if not github_token:
                return Response({'error': 'GitHub token not found for this user.'}, status=status.HTTP_400_BAD_REQUEST)
        except Profile.DoesNotExist:
            return Response({'error': 'Profile not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

        repo_headers = {'Authorization': f'token {github_token}', 'Accept': 'application/vnd.github.v3+json'}
        repo_res = requests.get('https://api.github.com/user/repos?sort=updated', headers=repo_headers)
        
        if repo_res.status_code != 200:
            return Response({'error': 'Failed to fetch repositories from GitHub.'}, status=repo_res.status_code)

        return Response(repo_res.json())
        # auth_header = request.headers.get('Authorization')
        # if not auth_header or not auth_header.startswith('Bearer '):
        #     return Response({'error': 'Authorization token not provided'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # token = auth_header.split(' ')[1]
        
        # repo_headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
        # repo_res = requests.get('https://api.github.com/user/repos?sort=updated', headers=repo_headers)
        
        # if repo_res.status_code != 200:
        #     return Response({'error': 'Failed to fetch repositories'}, status=repo_res.status_code)

        # return Response(repo_res.json())
def robust_b64decode(s):
    """A more robust base64 decoder that handles padding errors."""
    # Strip any whitespace from the input string
    s = s.strip()
    # Add padding if it's missing. A valid base64 string's length is a multiple of 4.
    padding = len(s) % 4
    if padding > 0:
        s += "=" * (4 - padding)
    return base64.b64decode(s).decode('utf-8')


class RepositoryFileView(APIView):
    def get(self, request, owner, repo_name, *args, **kwargs):
        
        user = request.user

        try:
            github_token = user.profile.github_access_token
            if not github_token:
                return Response({'error': 'GitHub token not found for this user.'}, status=status.HTTP_400_BAD_REQUEST)
        except Profile.DoesNotExist:
            return Response({'error': 'Profile not found for this user.'}, status=status.HTTP_404_NOT_FOUND)
        
        file_path = "serverless.yml"
        github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}"
        headers = {'Authorization': f'token {github_token}', 'Accept': 'application/vnd.github.v3+json'}

        try:
            res = requests.get(github_api_url, headers=headers)
            res.raise_for_status() 

            file_data = res.json()
            base64_content = file_data.get('content')
            
            if not base64_content:
                return Response({'error': 'File content is empty or invalid.'}, status=status.HTTP_400_BAD_REQUEST)

            decoded_content = robust_b64decode(base64_content)
            
            return Response({'filename': file_data.get('name'), 'content': decoded_content})

        except requests.exceptions.HTTPError as e:
            # This block now handles all non-200 responses from GitHub
            status_code = e.response.status_code
            if status_code == 404:
                error_message = f"'{file_path}' not found in this repository."
            elif status_code == 403:
                error_message = "Permission denied. Your token may not have access to this repository."
            else:
                error_message = "An unexpected error occurred when fetching from GitHub."
            
            return Response({'error': error_message, 'details': e.response.json()}, status=status_code)

        except (base64.binascii.Error, UnicodeDecodeError) as e:
            # This block specifically catches errors during the decoding process
            return Response(
                {'error': 'Failed to decode file content.', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            # A final catch-all for any other unexpected errors
            return Response(
                {'error': 'An internal server error occurred.', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ProfileSettingsView(APIView):
    """
    Allows authenticated users to retrieve and update their profile settings,
    specifically for AWS integration.
    """
    # This ensures only users with a valid Optifuse API token can access this view.
    # The default authentication class (TokenAuthentication) from settings.py will be used.
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests. Retrieves the current user's profile data.
        """
        # Because we use TokenAuthentication, DRF automatically finds the user
        # associated with the token and attaches it to the request object.
        user = request.user
        
        try:
            # We use select_related('user') for a small performance optimization.
            # It fetches the related User object in the same database query.
            profile = Profile.objects.select_related('user').get(user=user)
            
            # Prepare the data to be sent back as JSON
            response_data = {
                'username': profile.user.username,
                'subscription': profile.subscription,
                'aws_role_arn': profile.aws_role_arn,
                # The user needs this ID to configure their AWS Role trust policy.
                # It must be a string for JSON serialization.
                'aws_external_id': str(profile.aws_external_id),
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Profile.DoesNotExist:
            # This case is unlikely if your login process is correct, but it's good practice.
            return Response({'error': 'Profile not found for the authenticated user.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests. Updates the user's AWS Role ARN.
        """
        user = request.user
        aws_role_arn = request.data.get('aws_role_arn')

        if not aws_role_arn or not isinstance(aws_role_arn, str):
            return Response(
                {'error': 'A valid aws_role_arn string is required in the request body.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            profile = Profile.objects.get(user=user)
            # Update the field and save the change to the database
            profile.aws_role_arn = aws_role_arn
            profile.save(update_fields=['aws_role_arn']) # More efficient save
            
            return Response(
                {'message': 'AWS Role ARN updated successfully.'},
                status=status.HTTP_200_OK
            )
        except Profile.DoesNotExist:
            return Response({'error': 'Profile not found for the authenticated user.'}, status=status.HTTP_404_NOT_FOUND)