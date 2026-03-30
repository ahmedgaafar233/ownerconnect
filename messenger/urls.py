from django.urls import path
from . import views

app_name = 'messenger'

urlpatterns = [
    path('', views.messenger_home, name='index'),
    path('t/<int:thread_id>/', views.thread_detail, name='thread_detail'),
    path('new/<int:user_id>/', views.create_direct_thread, name='new_direct'),
]
