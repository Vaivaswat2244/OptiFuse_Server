# optifuse/server/core/urls.py
from django.urls import path
from .views import GitHubLogin, RepositoryListView

urlpatterns = [
    path('auth/github/', GitHubLogin.as_view(), name='github_login'),
    path('repositories/', RepositoryListView.as_view(), name='repository_list'),
]