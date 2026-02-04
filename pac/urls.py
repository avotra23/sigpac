"""
URL configuration for sigpac project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from .views import *

app_name = 'pac'
urlpatterns = [
     #URL de base
    path('',index_choix,name="index_choix"),

     #Passage apres login
    path('accueil/',accueil,name="accueil"),

    #Plainte
    #--Plainte anonyme
    path('anonyme/',anonyme,name="anonyme"),
    #--Plainte suivie
    path('acc_pub/',public,name="public"),
    #--Plainte opj
    path('acc_opj/',opj_list_view,name="opj"),

    #--Suppression plainte
    path('supprimer_plainte/<int:plainte_id>/', supprimer_plainte, name="supprimer_plainte"),
    #--Detail plainte
    path('detailp/', detailp ,name="detailp"),
    #--API Plainte
    path('api/public/plaintes/', api_public_plaintes, name='api_public_plaintes'), 
    path('api/public/plaintes/<int:plainte_id>/', api_public_plaintes, name='api_public_delete'),
    path('api/plaintes/anonyme/', plainte_anonyme_api, name='api_plainte_anonyme'),
    # Route pour l'API (utilisée par AJAX)
    path('api/opj/',api_opj_views, name='api_opj_views'),
    path('api/opj/<int:pk>/',api_opj_views, name='api_opj_delete'),

    #DCN
    path('acc_dcn/',acc_dcn,name="dcn"),
    path('api/dcn/plaintes/', api_dcn_plaintes, name='api_dcn_plaintes'),
    #procureur
    path('acc_proc/',acc_procureur,name="procureur"),

    #greffier
    path('acc_gre/',acc_greffier, name="greffier"),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)