"""
URL configuration for chatbot app
"""
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/chatbot/message/', views.chatbot_api, name='chatbot_api'),
    path('debug-categories/', views.debug_categories, name='debug_categories'),
    path('api/chatbot/feedback/', views.chatbot_feedback, name='chatbot_feedback'),
]
