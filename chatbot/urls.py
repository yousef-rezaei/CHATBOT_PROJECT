"""
URL configuration for chatbot app
"""
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/chatbot/message/', views.chatbot_api, name='chatbot_api'),
]
