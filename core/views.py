from decouple import config
import requests
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import Profile

class GitHubLogin(APIView):
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
        print("-----------------------------")
        print("i dont know shit anymore.... ")
        access_token = token_data.get('access_token')

        if not access_token:
            return Response({'error': 'Could not retrieve access token'}, status=status.HTTP_400_BAD_REQUEST)

        user_headers = {'Authorization': f'token {access_token}', 'Accept': 'application/vnd.github.v3+json'}
        user_res = requests.get('https://api.github.com/user', headers=user_headers)
        user_data = user_res.json()

        username = user_data.get('login')
        user, created = User.objects.get_or_create(username=username)

        if created:
            user.email = user_data.get('email')
            user.set_unusable_password()
            user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.github_access_token = access_token
        profile.save()

        return Response({
            'username': user.username,
            'access_token': access_token,
        })

class RepositoryListView(APIView):
    def get(self, request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization token not provided'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token = auth_header.split(' ')[1]
        
        repo_headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
        repo_res = requests.get('https://api.github.com/user/repos?sort=updated', headers=repo_headers)
        
        if repo_res.status_code != 200:
            return Response({'error': 'Failed to fetch repositories'}, status=repo_res.status_code)

        return Response(repo_res.json())
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
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Authorization token not provided'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token = auth_header.split(' ')[1]
        file_path = "serverless.yml"
        github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}"
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
        }

        try:
            # Make the request to GitHub
            res = requests.get(github_api_url, headers=headers)
            # This will raise an HTTPError for 4xx/5xx responses (like 404, 403)
            res.raise_for_status() 

            # If we get here, the status code was 200 OK
            file_data = res.json()
            base64_content = file_data.get('content')
            
            if not base64_content:
                return Response(
                    {'error': 'File content is empty or invalid.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use our robust decoder
            decoded_content = robust_b64decode(base64_content)
            
            return Response({
                'filename': file_data.get('name'),
                'content': decoded_content,
            })

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