from decouple import config
import requests
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