
from django.urls import path
from .views import LiveSimulationView

# This is a list of URL patterns for the 'simulation' app.
urlpatterns = [
    path('live/', LiveSimulationView.as_view(), name='run_live_simulation'),
]