from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth import login,logout,authenticate
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token
from django.db.models import Count, Max
import base64
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from django.db import transaction
from django.urls import reverse
from .models import *
from .forms import *
from django.contrib import messages
from .decorators import *
from django.utils import timezone
# Gestion de log
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

# Gestion DRF
from rest_framework.authtoken.models import Token  


# ----API MODULE  + Ajout de serializers
from rest_framework.decorators import api_view, permission_classes, parser_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    UtilisateurSerializer,PublicInscriptionSerializer,ProfileUpdateSerializer,OPJInscriptionSerializer
)

from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password


#Connexion
def login_view(request):
    context = {
                'erreur':'vraie'
            }      
    return render(request, 'utilisateur/login_api.html',context)

#Deconnexion
def logout_view(request):
    logout(request)
    return redirect('utilisateur:login')


#Gestion utilisateur
#-Incription public
def inscriptionpub(request):
    form = PublicInscription()
    return render(request,'utilisateur/inscription.html',{'form':form,'name':'PUBLIC','url':'api_inscription'})

#-Inscription OPJ
def inscriptionopj(request):
    form = OPJCreationForm()
    return render(request,'utilisateur/inscription.html',{'form':form,'name':'OPJ','url':'api_inscription_opj'})
#-Inscription par admin
def inscriptionadmin(request):
    if request.method == 'POST':
        form = AdminCreationForm(request.POST)
        if form.is_valid():
           
            group = form.cleaned_data['group_choice'] 
            user = form.save()
            if group:
                user.groups.add(group)
            return redirect('utilisateur:acc_admin') 
    else :
        form = AdminCreationForm()
    context = {
        'form': form,
        'title': "Inscription du personnel",
    }
    return render(request, 'utilisateur/inscription.html', context)

@login_required
@user_passes_test(is_admin, login_url='accueil')
@transaction.atomic
def acc_admin(request, mode='utilisateur'): 
    
    data_list = []
    title = ""
    template_name = 'utilisateur/acc_admin.html' # Le même template
    all_groups = None

    if mode == 'utilisateur':
        # 1. Liste des Utilisateurs
        title = "LISTE DES UTILISATEURS"
        queryset = Utilisateur.objects.all().select_related('poste', 'localite').prefetch_related('groups').order_by('-id')
        
        # Récupération du filtre 'group_id' depuis l'URL (?group_id=...)
        selected_group = request.GET.get('group_id')
        if selected_group:
            queryset = queryset.filter(groups__id=selected_group)
        
        data_list = queryset
        all_groups = Group.objects.all() # Liste pour le template
        form = " "
    elif mode == 'groupe':
        # 2. Liste des Groupes avec le nombre d'utilisateurs
        title = "LISTE DES GROUPES D'UTILISATEURS"
        data_list = Group.objects.annotate(user_count=Count('utilisateur')) 
        form = " "
    elif mode == 'localite':
        # 3. Liste des Localités avec le nombre d'utilisateurs
        title = "LISTE DES LOCALITÉS"
       
        data_list = Localite.objects.annotate(user_count=Count('utilisateur')) 
        form = " "
    elif mode =='ajout':
        form = AdminCreationForm()
    elif mode == 'RA':
        title = "REGISTRE D'ARRIVE"
        form =" "
        plaintes_filtrees = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite
            ).order_by('-date_arrivee')
        data_list = plaintes_filtrees
    elif mode == 'log':
        form = " "
        from django.core.paginator import Paginator
        title = "JOURNAL D'AUDIT"

        logs = LogEntry.objects.select_related('actor', 'content_type').order_by('-timestamp')

        actor_id   = request.GET.get('actor')
        model_name = request.GET.get('model')
        action     = request.GET.get('action')
        date_debut = request.GET.get('date_debut')
        date_fin   = request.GET.get('date_fin')
        search     = request.GET.get('q')

        if actor_id:
            logs = logs.filter(actor_id=actor_id)
        if model_name:
            logs = logs.filter(content_type__model=model_name)
        if action in ['0', '1', '2']:
            logs = logs.filter(action=int(action))
        if date_debut:
            logs = logs.filter(timestamp__date__gte=date_debut)
        if date_fin:
            logs = logs.filter(timestamp__date__lte=date_fin)
        if search:
            logs = logs.filter(
                Q(actor__email__icontains=search) |
                Q(object_repr__icontains=search)  |
                Q(changes__icontains=search)
            )

        paginator = Paginator(logs, 50)
        data_list = paginator.get_page(request.GET.get('page', 1))

        # all_groups réutilisé pour transporter les données de filtre
        all_groups = {
            'utilisateurs' : Utilisateur.objects.all().order_by('nom'),
            'content_types': ContentType.objects.filter(
                                logentry__isnull=False
                             ).distinct().order_by('model'),
            'filters': {
                'actor'     : actor_id,
                'model'     : model_name,
                'action'    : action,
                'date_debut': date_debut,
                'date_fin'  : date_fin,
                'q'         : search,
            }
        }
    context = {
        'user': request.user,
        'data_list': data_list,
        'title': title,
        'mode': mode,         
        'form' : form,
        'all_groups' : all_groups,
        'groups' : "admin",
    }
    

    return render(request, template_name, context)

# --- Vue pour la MODIFICATION d'un utilisateur ---
# ---- MODIFICATION DES VUES EXISTANTES POUR LOGGUER MANUELLEMENT ----

@login_required
@user_passes_test(is_admin, login_url='accueil')
@transaction.atomic
def modifier_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    template_name = 'utilisateur/acc_admin.html'

    if request.method == 'POST':
        form = AdminModificationForm(request.POST, instance=utilisateur)
        if form.is_valid():
            form.save()
            # ── LOG MANUEL modification utilisateur ──
            LogEntry.objects.log_create(
                instance=utilisateur,
                action=LogEntry.Action.UPDATE,
                actor=request.user,
                changes=f"Modification de l'utilisateur {utilisateur.email} (id={utilisateur.pk})"
            )
            messages.success(request, f"L'utilisateur {utilisateur.pk} a été modifié avec succès.")
            return redirect('utilisateur:acc_admin', mode='utilisateur')
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = AdminModificationForm(instance=utilisateur)

    champs_speciaux_a_exclure = ['groups', 'is_active', 'is_superuser']
    context = {
        'user'                   : request.user,
        'data_list'              : [],
        'title'                  : f"MODIFIER L'UTILISATEUR id: {utilisateur.pk}",
        'form'                   : form,
        'mode'                   : 'modifier',
        'utilisateur_a_modifier' : utilisateur,
        'champs_speciaux_a_exclure': champs_speciaux_a_exclure,
    }
    return render(request, "utilisateur/acc_admin.html", context)



# --- Vue pour la SUPPRESSION d'un utilisateur ---
@login_required
@user_passes_test(is_admin, login_url='accueil')
@transaction.atomic
def supprimer_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)

    if request.method == 'POST':
        if utilisateur.is_superuser:
            messages.error(request, f"Impossible de supprimer le superutilisateur {utilisateur.email}.")
            return redirect('utilisateur:acc_admin', mode='utilisateur')

        email_supprime = utilisateur.email
        # ── LOG MANUEL suppression utilisateur ──
        LogEntry.objects.log_create(
            instance=utilisateur,
            action=LogEntry.Action.DELETE,
            actor=request.user,
            changes=f"Suppression de l'utilisateur {email_supprime} (id={pk})"
        )
        utilisateur.delete()
        messages.success(request, f"L'utilisateur {email_supprime} a été supprimé avec succès.")

    return redirect('utilisateur:acc_admin', mode='utilisateur')

#---- Vue pour la gestion de log 

@login_required
@user_passes_test(is_admin, login_url='accueil')
def audit_log(request):
    logs = LogEntry.objects.select_related('actor', 'content_type').order_by('-timestamp')

    actor_id   = request.GET.get('actor')
    model_name = request.GET.get('model')
    action     = request.GET.get('action')
    date_debut = request.GET.get('date_debut')
    date_fin   = request.GET.get('date_fin')
    search     = request.GET.get('q')

    if actor_id:
        logs = logs.filter(actor_id=actor_id)
    if model_name:
        logs = logs.filter(content_type__model=model_name)
    if action in ['0', '1', '2']:
        logs = logs.filter(action=int(action))
    if date_debut:
        logs = logs.filter(timestamp__date__gte=date_debut)
    if date_fin:
        logs = logs.filter(timestamp__date__lte=date_fin)
    if search:
        logs = logs.filter(
            Q(actor__email__icontains=search) |
            Q(object_repr__icontains=search)  |
            Q(changes__icontains=search)
        )

    from django.core.paginator import Paginator
    paginator  = Paginator(logs, 50)
    logs_page  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'logs'          : logs_page,
        'utilisateurs'  : Utilisateur.objects.all().order_by('nom'),
        'content_types' : ContentType.objects.filter(logentry__isnull=False).distinct().order_by('model'),
        'filters': {
            'actor'     : actor_id,
            'model'     : model_name,
            'action'    : action,
            'date_debut': date_debut,
            'date_fin'  : date_fin,
            'q'         : search,
        },
        'groups': 'admin',
    }
    return render(request, 'utilisateur/audit_log.html', context)


@login_required
@user_passes_test(is_admin, login_url='accueil')
def audit_detail_objet(request, content_type_id, object_id):
    ct   = get_object_or_404(ContentType, pk=content_type_id)
    logs = LogEntry.objects.filter(
        content_type=ct,
        object_id=str(object_id)
    ).select_related('actor').order_by('-timestamp')

    context = {
        'logs'      : logs,
        'model_name': ct.model,
        'object_id' : object_id,
        'groups'    : 'admin',
    }
    return render(request, 'utilisateur/audit_detail.html', context)

# ---- FIN VUE AUDIT LOG ----


# --- FIN VUE LOG


#----API--------
#--API RESET PASSWORD md
@api_view(['POST'])
def reset_password_api(request):
    email = request.data.get('email')
    telephone = request.data.get('telephone') # Récupération du tel
    new_password = request.data.get('password')
    
    try:
        # On identifie l'utilisateur par Email + Téléphone
        user = Utilisateur.objects.get(email=email, telephone=telephone)
        
        # Règle des 3 mois
        if not user.peut_changer_mdp():
            prochaine_date = user.last_password_change + timedelta(days=90)
            jours_restants = (prochaine_date - timezone.now()).days
            return Response({
                "detail": f"Sécurité : Modification possible dans {max(1, jours_restants)} jours."
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Mise à jour
        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save()
        
        return Response({"detail": "Mot de passe modifié avec succès ! Redirection..."})
        
    except Utilisateur.DoesNotExist:
        return Response({
            "detail": "Les informations fournies ne correspondent pas à nos registres."
        }, status=status.HTTP_404_NOT_FOUND)
#APILogin avant drf
'''
@csrf_exempt
@api_view(['POST'])
def api_login_view(request):
    print("REQUETE RECUE !")
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response(
            {"detail": "Email et mot de passe sont requis."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, email=email, password=password)
    if user is not None:
        login(request, user)
        role = 'simple' 
        if is_admin(user):
            role = 'admin'
        elif is_procureur(user):
            role = 'procureur'
        elif is_greffier(user):
            role = 'greffier'
        elif is_public(user):
            role = 'public'
        elif is_opj(user):
            role = 'opj'
        elif is_dcn(user): 
            role = 'dcn'
            
        user_data = UtilisateurSerializer(user).data
        csrf_token = get_token(request)
        return Response({
            "detail": f"Connexion réussie. Bienvenue, {user.nom}.",
            "user": user_data,
            "role": role, 
            "token" : csrf_token
        })
    else:
        return Response(
            {"detail": "Identifiants invalides."}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
'''
# APILogin apres DRF
from rest_framework.authtoken.models import Token  # ← Ajouter cet import en haut

@csrf_exempt
@api_view(['POST'])
def api_login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response(
            {"detail": "Email et mot de passe sont requis."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, email=email, password=password)
    if user is not None:
        login(request, user)  # ← Conservé : session web toujours fonctionnelle
        
        # Rôle (inchangé)
        role = 'simple' 
        if is_admin(user):       role = 'admin'
        elif is_procureur(user): role = 'procureur'
        elif is_greffier(user):  role = 'greffier'
        elif is_public(user):    role = 'public'
        elif is_opj(user):       role = 'opj'
        elif is_dcn(user):       role = 'dcn'
            
        user_data = UtilisateurSerializer(user).data
        csrf_token = get_token(request)
        
        # ← AJOUT : Créer ou récupérer le DRF Token pour Android/WebSocket
        drf_token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            "detail": f"Connexion réussie. Bienvenue, {user.nom}.",
            "user": user_data,
            "role": role, 
            "token": csrf_token,           # ← Conservé pour le web
            "auth_token": drf_token.key,   # ← NOUVEAU : pour Android + WebSocket
        })
    else:
        return Response(
            {"detail": "Identifiants invalides."}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

'''API LOGOUT AVANT DRF
@api_view(['POST','GET'])
def api_logout_view(request):
    logout(request)
    return redirect("utilisateur:login")
 '''

# api logout avec DRF
@api_view(['POST', 'GET'])
def api_logout_view(request):
    # Supprimer le DRF Token si existant (déconnexion Android)
    if request.user.is_authenticated:
        try:
            from rest_framework.authtoken.models import Token
            Token.objects.filter(user=request.user).delete()
        except Exception:
            pass
    
    logout(request)  # ← Session web toujours déconnectée
    return redirect("utilisateur:login")

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny]) # Permet l'accès sans être connecté
def api_pinscription_view(request):
    serializer = PublicInscriptionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Utilisateur créé avec succès",
            "redirect": "/utilisateur/login/" # Optionnel pour le frontend
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny]) # Permet l'accès sans être connecté
def api_inscriptionopj_view(request):
    serializer = OPJInscriptionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Utilisateur créé avec succès",
            "redirect": "/utilisateur/login/" # Optionnel pour le frontend
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'PUT']) # Accepter POST pour faciliter l'envoi du FormData
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def update_profile_api(request):
    user = request.user
    
    if request.method in ['POST', 'PUT']:
        # On passe partial=True pour permettre de ne modifier que certains champs
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profil mis à jour !"}, status=200)
        return Response(serializer.errors, status=400)
    
    # Pour le GET (si besoin d'initialiser le formulaire)
    serializer = ProfileUpdateSerializer(user)
    return Response(serializer.data)


