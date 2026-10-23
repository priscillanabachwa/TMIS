from django.urls import path, include
from django.contrib.auth import views as auth
urlpatterns = [path('login/',auth.LoginView.as_view(template_name='training/login.html'),name='login'),path('logout/',auth.LogoutView.as_view(),name='logout'),path('',include('training.urls'))]
