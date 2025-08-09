from django.urls import path
from . import views

app_name = 'botapp'

urlpatterns = [
    path('statistics/', views.statistics_dashboard, name='statistics_dashboard'),
    path('statistics/api/', views.statistics_api, name='statistics_api'),
    path('analytics/users/', views.user_analytics, name='user_analytics'),
    path('analytics/downloads/', views.download_analytics, name='download_analytics'),
]
