from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth import login,logout,authenticate
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token
from django.db.models import Count, Max
import base64
from django.db import transaction
from django.urls import reverse
from .models import *
from .forms import *
from django.contrib import messages
from .decorators import *
from django.utils import timezone
import qrcode
from io import BytesIO

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

    if mode == 'utilisateur':
        # 1. Liste des Utilisateurs
        title = "LISTE DES UTILISATEURS"
        data_list = Utilisateur.objects.all().select_related('poste', 'localite').prefetch_related('groups')
        
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
        form =" "
        plaintes_filtrees = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite
            ).order_by('-date_arrivee')
        data_list = plaintes_filtrees
    context = {
        'user': request.user,
        'data_list': data_list,
        'title': title,
        'mode': mode,         
        'form' : form,
    }
    

    return render(request, template_name, context)

# --- Vue pour la MODIFICATION d'un utilisateur ---
@login_required
@user_passes_test(is_admin, login_url='accueil')
@transaction.atomic
def modifier_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    
    # Le template à utiliser est maintenant le même que pour acc_admin
    template_name = 'utilisateur/acc_admin.html' 
    
    if request.method == 'POST':
        
        form = AdminModificationForm(request.POST, instance=utilisateur)
        if form.is_valid():
            form.save()
            messages.success(request, f"L'utilisateur **{utilisateur.pk}** a été modifié avec succès.")
            
            return redirect('acc_admin', mode='utilisateur') 
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = AdminModificationForm(instance=utilisateur)
        
    # NOUVEAU : Définissez ici les champs à exclure du rendu automatique
    champs_speciaux_a_exclure = ['groups', 'is_active', 'is_superuser']

    context = {
        'user': request.user,
        'data_list': [],
        'title': f"MODIFIER L'UTILISATEUR id: {utilisateur.pk}",
        'form': form,
        'mode': 'modifier',
        'utilisateur_a_modifier': utilisateur,
        'champs_speciaux_a_exclure': champs_speciaux_a_exclure, 
    }
    
    return render(request, "utilisateur/acc_admin.html", context)
    
# --- Vue pour la SUPPRESSION d'un utilisateur ---
@login_required
@user_passes_test(is_admin, login_url='accueil')
@transaction.atomic
def supprimer_utilisateur(request, pk):
    # Récupère l'utilisateur ou renvoie une 404
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    
    # On vérifie que c'est une requête POST (sécurité)
    if request.method == 'POST':
        # Empêche la suppression de l'utilisateur actuellement connecté ou du superutilisateur (si vous voulez)
        if utilisateur.is_superuser:
             messages.error(request, f"Impossible de supprimer le superutilisateur {utilisateur.email}.")
             return redirect('acc_admin', mode='utilisateur')
        
        email_supprime = utilisateur.email
        utilisateur.delete()
        messages.success(request, f"L'utilisateur **{email_supprime}** a été supprimé avec succès.")
        
    return redirect('acc_admin', mode='utilisateur')




#----API--------

#APILogin
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

@api_view(['POST','GET'])
def api_logout_view(request):
    logout(request)
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