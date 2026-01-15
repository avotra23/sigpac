from django.urls import path
from .views import *
app_name = 'utilisateur'

urlpatterns = [

    #Connexion - deconnexion
    path('login/',login_view,name="login"),
    path('logout/',logout_view,name="logout"),

    #Gestion utilisateur
    #--Inscription public
    path('inscriptionp/',inscriptionpub, name="inscriptionpub"),
    #--Inscription par admin
    path('inscription/',inscriptionadmin,name="inscription"),
    
    #Administrateur
    path('acc_admin',acc_admin,name="acc_admin"),
    path('acc_admin/<str:mode>/', acc_admin, name='acc_admin'),
    path('gestion/utilisateur/modifier/<int:pk>/', modifier_utilisateur, name='modifier_utilisateur'),
    path('gestion/utilisateur/supprimer/<int:pk>/', supprimer_utilisateur, name='supprimer_utilisateur'),
    
# API URL
    #-Authentification
    path('api/login/', api_login_view, name='api_login'),
    path('api/logout/', api_logout_view, name='api_logout'),
    path('api/inscription/', api_pinscription_view, name='api_inscription'),
    path('api/update_profile/',update_profile_api,name="update_profil"),
]