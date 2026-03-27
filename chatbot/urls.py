from django.urls import path
from . import views
from . import analytics_views

app_name = 'chatbot'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/chatbot/message/', views.chatbot_api, name='chatbot_api'),
    path('debug-categories/', views.debug_categories, name='debug_categories'),
    path('api/chatbot/feedback/', views.chatbot_feedback, name='chatbot_feedback'),
    
    # Sessions
    path('api/analytics/sessions/', analytics_views.list_sessions, name='analytics_list_sessions'),
    path('api/analytics/sessions/<str:session_id>/', analytics_views.get_session_detail, name='analytics_session_detail'),
    # Messages & Logs
    path('api/analytics/messages/<int:message_id>/console/', analytics_views.get_message_console_logs, name='analytics_message_console'),
    # Statistics
    path('api/analytics/stats/', analytics_views.get_stats, name='analytics_stats'),
    # Search
    path('api/analytics/search/', analytics_views.search_logs, name='analytics_search'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
]