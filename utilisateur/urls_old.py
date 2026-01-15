from django.urls import path
from .views import *
urlpatterns = [
    #URL de base
    path('',none,name="none"),

    path('login/',login_view,name="login"),
    path('logout/',logout_view,name="logout"),
    path('inscriptionp/',inscriptionpub, name="inscriptionpub"),
    path('inscription/',inscriptionadmin,name="inscription"),
    path('accueil/',accueil,name="accueil"),

    #Administrateur
    path('acc_admin',acc_admin,name="acc_admin"),
    path('acc_admin/<str:mode>/', acc_admin, name='acc_admin'),
    path('gestion/utilisateur/modifier/<int:pk>/', modifier_utilisateur, name='modifier_utilisateur'),
    path('gestion/utilisateur/supprimer/<int:pk>/', supprimer_utilisateur, name='supprimer_utilisateur'),
    
    #Simple utilisateur
    path('acc_simp/',simple,name="simple"),

    #Public 
    path('acc_pub/',public,name="public"),
    path('anonyme/',anonyme,name="anonyme"),
    path('supprimer_plainte/<int:plainte_id>/', supprimer_plainte, name="supprimer_plainte"),

    #DCN
    path('acc_dcn/',acc_dcn,name="acc_dcn"),

    #procureur
    path('acc_proc',acc_procureur,name="acc_procureur"),

    #Greffier
    path('acc_greffier',acc_greffier,name="acc_greffier"),
# LES API URLS -----------------------------------------------------
# Authentification
    path('api/login/', api_login_view, name='api_login'),
    path('api/logout/', api_logout_view, name='api_logout'),
    path('api/inscription/public/', api_inscriptionpub, name='api_inscriptionpub'),
    # Ajoutez les autres inscriptions (opj, admin) ici

    # Accueil / Rôle
    path('api/accueil/', api_accueil, name='api_accueil'),
    
    # Vues Administrateur
    path('api/admin/listes/', api_acc_admin, name='api_acc_admin'),
    # Vues Public (Plaintes)
    # GET: Liste des plaintes ou info formulaire (?mode=form)
    # POST: Créer une nouvelle plainte
    path('api/public/plaintes/', api_public_plaintes, name='api_public_plaintes'), 
    path('api/plaintes/anonyme/', plainte_anonyme_api, name='api_plainte_anonyme'),
    # Vues Simples
    path('api/simple/', api_simple_view, name='api_simple'),

# LES API URLS FIN-----------------------------------------------------
]
