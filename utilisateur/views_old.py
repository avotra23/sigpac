
from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth import login,logout,authenticate
from django.middleware.csrf import get_token
from django.contrib.auth.models import Group
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max
from django.views.decorators.csrf import csrf_exempt
from .models import *
from .forms import *
from .decorators import *
from django.utils import timezone
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
import base64
from django.urls import reverse
# Create your views here.

# ----API MODULE  + Ajout de serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    UtilisateurSerializer, GroupSerializer, LocaliteSerializer, 
    PlainteSerializer, PlainteCreationSerializer
)

# ---- FIN MODULE API

#Connexion
def login_view(request):
    context = {
                'erreur':'vraie'
            }
    if request.method == 'POST':
        em = request.POST.get('email')
        passe = request.POST.get('password')

        user = authenticate(request, email = em, password = passe)
        if user is not None :
            login(request,user)
            messages.success(request, f"Connexion reussi. Bienvenue, {user.nom}")
            return redirect('accueil')
        else :
            context = {
                'erreur':'erreur'
            }
         
    return render(request, 'utilisateur/login.html',context)

#Deconnexion
def logout_view(request):
    logout(request)
    return redirect('login')

#Inscription
def inscriptionpub(request):
    if request.method == 'POST':
        form = PublicInscription(request.POST)

        if form.is_valid():
            user = form.save()

            
            public_group = Group.objects.get(name='public')
            public_group.utilisateur_groups.add(user)
            return redirect('login')
    else:
        form = PublicInscription()
    return render(request,'utilisateur/inscription.html',{'form':form,'name':'pub'})

def inscriptionopj(request):
    if request.method == 'POST':
        form = OPJCreationForm(request.POST)

        if form.is_valid():
            user = form.save()

            public_group = Group.objects.get(name='opj')
            public_group.utilisateur_groups.add(user)
            return redirect('login')
    else:
        form = OPJCreationForm()
    return render(request,'utilisateur/inscription.html',{'form':form,'name':'opj'})

def inscriptionadmin(request):
    if request.method == 'POST':
        form = AdminCreationForm(request.POST)
        if form.is_valid():
           
            group = form.cleaned_data['group_choice'] 
            user = form.save()
            if group:
                user.groups.add(group)
            return redirect('acc_admin') 
    else :
        form = AdminCreationForm()
    context = {
        'form': form,
        'title': "Inscription du personnel",
    }
    return render(request, 'utilisateur/inscription.html', context)


@login_required
def accueil(request):
    user = request.user

    if is_admin(user):
        return redirect('acc_admin')
    elif is_procureur(user):
        return redirect('acc_procureur')
    elif is_greffier(user):
        return redirect('acc_greffier')
    elif is_public(user):
        return redirect('public')
    elif is_dcn(user):
        return redirect('acc_dcn')
    if is_opj(user):
        return redirect('acc_opj')
    else :
        return redirect('simple')


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

@login_required
@user_passes_test(is_simple, login_url='accueil') 
def simple(request):
    
    # 1. Gestion de la soumission du formulaire (POST)
    if request.method == 'POST':
        form = RegistreArriveForm(request.POST) 
        
        if form.is_valid():
            # Créer l'objet mais ne pas encore le sauvegarder en base de données
            registre = form.save(commit=False)
            
            # --- AJOUT CRUCIAL 1: Champs automatiques/de traçabilité ---
            # Définir l'utilisateur créateur (nécessaire avant la numérotation)
            registre.utilisateur_creation = request.user 
            
            # La date d'arrivée est déjà gérée par default=timezone.now dans le modèle 
            # (si le champ n'est pas inclus dans le formulaire).
            
            # --- AJOUT CRUCIAL 2: Sauvegarde ---
            # Appeler save(). La méthode save du modèle se charge de la numérotation 
            # (n_enr_arrive) et effectue la double sauvegarde si c'est une création.
            registre.save() 
            
            messages.success(request, f"Registre Arrivé **N° {registre.n_enr_arrive}** enregistré avec succès.")
            
            # Redirige vers la liste des registres (mode='list' par défaut)
            return redirect('simple') 
        
        # Si le formulaire n'est pas valide, nous devons passer le formulaire au contexte
        else:
            # Pour l'affichage en cas d'erreur de validation, nous passons le formulaire
            # La logique de re-display ci-dessous gère 'mode'='form' par défaut
            pass
    
    # 2. Gestion de l'affichage (GET ou POST invalide)
    
    mode = request.GET.get('mode', 'list')
    form = RegistreArriveForm() # Initialisation par défaut pour éviter les erreurs de variable non définie
    
    # Si nous arrivons ici après un POST invalide, 'form' est déjà l'instance du formulaire avec erreurs.
    if request.method != 'POST':
        form = RegistreArriveForm() # Réinitialiser uniquement en cas de requête GET
        
    context = {
        'user': request.user,
        'mode': mode,
        'menu_active': 'arrive',
    }
    
    if mode == 'list':
        # Mode LISTE: Récupération des registres
        # OPTIONNEL: Filtrer par localité si l'utilisateur simple ne voit que les siens
        context['registres'] = RegistreArrive.objects.filter(
             utilisateur_creation__localite=request.user.localite
         ).order_by('-date_arrivee')
        
    elif mode == 'form' or request.method == 'POST': # Affiche le formulaire (y compris en cas d'erreur POST)
        try:
            last_enr_id = RegistreArrive.objects.aggregate(Max('id'))['id__max']
            next_enr = str((last_enr_id or 0) + 1).zfill(4)
        except Exception:
            next_enr = "0001" # Cas où la table est vide

        context['form'] = form # Soit l'instance vide (GET), soit l'instance avec les erreurs (POST)
        context['date_arrivee_systeme'] = timezone.now().strftime("%Y-%m-%d") 
        context['n_enr_provisoire'] = next_enr
    validation_id = request.GET.get('valider_id')
    if validation_id:
        try:
            registre = RegistreArrive.objects.get(pk=validation_id, 
                                                  utilisateur_creation__localite=request.user.localite,
                                                  est_valide=False) # Assurez-vous qu'il n'est pas déjà validé
            
            n_ra = registre.attribuer_ra() # Appelle la méthode du modèle
            messages.success(request, f"Registre Arrivé validé et numéroté : **{n_ra}**.")
            
        except RegistreArrive.DoesNotExist:
            messages.error(request, "Le registre à valider n'existe pas ou est déjà validé.")
        
        # Redirige toujours vers la liste
        return redirect('simple')     
    # Le template est maintenant unique
    return render(request, 'utilisateur/simple.html', context)

@login_required
@user_passes_test(is_public, login_url='accueil') 
def public(request):
    # Récupération des paramètres de mode et d'ID
    mode = request.GET.get('mode', 'list') 
    plainte_id = request.GET.get('plainte_id')
    detail_id = request.GET.get('detail_id')
    
    context = {
        'user': request.user,
        'mode': mode,
    }

    # 1. GESTION DE LA SOUMISSION DU FORMULAIRE (AJOUT/MODIFICATION)
    if request.method == 'POST':
        plainte_instance = None
        is_modification = False
        
        if plainte_id:
            plainte_instance = get_object_or_404(Plainte, pk=plainte_id)
            is_modification = True
        
        form = PlainteForm(request.POST,request.FILES ,instance=plainte_instance)
        
        if form.is_valid():
            # --- 🔑 LOGIQUE D'INJECTION DE L'UTILISATEUR CONNECTÉ ---
            plainte = form.instance
            
            if not is_modification:
                # Création (Ajout) : Définir l'utilisateur de création
                # Ce champ n'est défini qu'une seule fois
                plainte.utilisateur_creation = request.user
            
            # Modification : Définir l'utilisateur de modification
            # Ce champ est mis à jour à chaque modification
            plainte.utilisateur_modification = request.user
            
            # Sauvegarder l'instance avec les champs utilisateur_creation/modification remplis
            plainte.save() 
            # Note: Si votre méthode save() du modèle Plainte est complexe (comme c'était le cas),
            # elle gérera la double sauvegarde pour le n_chrono_tkk
            
            
            
            if is_modification:
                messages.success(request, f'La plainte N° {plainte.n_chrono_tkk} a été modifiée avec succès.')
            else:
                url_de_suivi = request.build_absolute_uri(reverse('public') + f"?mode=list&detail_id={plainte.pk}")
                
                # 2. Génération du QR Code
                qr = qrcode.QRCode(
                    version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4,
                )
                qr.add_data(url_de_suivi)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                # 3. Sauvegarde de l'image en mémoire et encodage en Base64
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # 4. Stocker les données de succès dans la session
                request.session['plainte_success'] = {
                    'n_chrono_tkk': plainte.n_chrono_tkk,
                    'qr_code_base64': qr_code_base64,
                    'url_de_suivi': url_de_suivi,
                    'mode_anonyme': False,
                }
            return redirect('public') # Rediriger vers la liste après succès

        
        context['form'] = form
       
    
    # 2. GESTION DE L'AFFICHAGE (GET)

    if mode == 'list':
        # Mode LISTE
        context['plaintes'] = request.user.plaintes_creees.all()
        
        if detail_id:
            try:
                context['plainte_detail'] = Plainte.objects.get(pk=detail_id)
            except Plainte.DoesNotExist:
                messages.error(request, "La plainte demandée n'existe pas.")

    elif mode == 'form':
        # Mode FORMULAIRE (Ajout ou Modification)
        
        plainte_instance = None
        if plainte_id:
            plainte_instance = get_object_or_404(Plainte, pk=plainte_id)
            context['form_title'] = "Modifier la Plainte"
            
        else:
            context['form_title'] = "Enregistrer une Nouvelle Plainte"
            
        # Création du formulaire (vide, pré-rempli, ou avec les erreurs si POST échoué)
        # Si 'form' existe déjà (suite à une erreur POST), on le réutilise, sinon on le crée.
        if 'form' not in context:
             form = PlainteForm(instance=plainte_instance)
        else:
            form = context['form'] # Récupère le formulaire avec les erreurs
        
        # Contexte supplémentaire pour l'affichage
        date_actuelle = timezone.now().strftime("%d/%m/%Y")
        prochain_chrono = f"DPL: PROVISOIRE/{timezone.now().year}"

        context['form'] = form
        context['n_chrono_tkk'] = plainte_instance.n_chrono_tkk if plainte_instance else prochain_chrono
        context['date_plainte'] = date_actuelle
        
    return render(request, 'utilisateur/acc_public.html', context)

def none(request):
    return render(request, 'utilisateur/none.html')
def anonyme(request):
    context = {}
    plainte_instance = None
    context['form_title'] = "Enregistrer une Nouvelle Plainte"
    if request.method == 'POST':
        plainte_instance = None
        form = PlainteForm(request.POST,request.FILES ,instance=plainte_instance)
        
        if form.is_valid():
            plainte = form.instance
            plainte.ny_mpitory = "Anonyme"
            plainte.est_anonyme = True
            # Sauvegarder l'instance avec les champs utilisateur_creation/modification remplis
            plainte.save() 
            messages.success(request, f'Votre plainte a été enregistrée avec succès sous le N° {plainte.n_chrono_tkk} !')
            # 1. Préparation des données pour le QR Code
            url_de_suivi = request.build_absolute_uri(reverse('anonyme') + f"?plainte_id={plainte.pk}") # Adapter ceci
            
            # 2. Génération du QR Code
            qr = qrcode.QRCode(
                version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4,
            )
            qr.add_data(url_de_suivi)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 3. Sauvegarde de l'image en mémoire et encodage en Base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # 4. Stocker les données de succès dans la session
            request.session['plainte_success'] = {
                'n_chrono_tkk': plainte.n_chrono_tkk,
                'qr_code_base64': qr_code_base64,
                'url_de_suivi': url_de_suivi,
                'mode_anonyme': True,
            }
            return redirect('anonyme')
        # Création du formulaire (vide, pré-rempli, ou avec les erreurs si POST échoué)
        # Si 'form' existe déjà (suite à une erreur POST), on le réutilise, sinon on le crée.
    if 'form' not in context:
        form = PlainteForm(instance=plainte_instance)
    else:
        form = context['form'] # Récupère le formulaire avec les erreurs
        
        # Contexte supplémentaire pour l'affichage
    date_actuelle = timezone.now().strftime("%d/%m/%Y")
    prochain_chrono = f"DPL: PROVISOIRE/{timezone.now().year}"

    context['form'] = form
    context['n_chrono_tkk'] = plainte_instance.n_chrono_tkk if plainte_instance else prochain_chrono
    context['date_plainte'] = date_actuelle
    return render(request, 'utilisateur/anonyme.html',context)

# --- VUE SÉPARÉE POUR LA SUPPRESSION ---
# @require_POST assure que la vue n'est accessible que via POST, ce qui est crucial pour la sécurité
@require_POST
def supprimer_plainte(request, plainte_id):
    """
    Vue dédiée à la suppression d'une plainte via une requête POST 
    (déclenchée après confirmation Swal).
    """
    
    # 1. Récupération de l'objet ou erreur 404
    plainte = get_object_or_404(Plainte, pk=plainte_id)
    plainte_chrono = plainte.n_chrono_tkk # Sauvegarder le chrono avant la suppression
    
    # 2. Suppression de l'objet
    plainte.delete()
    
    # 3. Message de succès et redirection
    messages.success(request, f'La plainte N° {plainte_chrono} a été supprimée avec succès.')
    return redirect('public')


@login_required
@user_passes_test(is_dcn, login_url='accueil')
def acc_dcn(request):
    mode = request.GET.get('mode')
    detail_id = request.GET.get('detail_id')
    context = {
        "user":request.user,
        "po": Plainte.objects.all()
    }
    if request.method == 'POST' and mode == 'dispatch':
        plainte_id = request.POST.get('idplainte')
        pac_destination = request.POST.get('pac')
        plainte_a_dispatcher = Plainte.objects.get(pk=plainte_id)

        print(plainte_id)
        plainte_a_dispatcher.statut = "DISPATCHE"
        plainte_a_dispatcher.pac_affecte = pac_destination
        plainte_a_dispatcher.save(update_fields=['statut'])
        return render(request, "utilisateur/acc_dcn.html",context)
    if mode == 'list':
        # Mode LISTE
        context['plaintes'] = Plainte.objects.all()
        
        if detail_id:
            try:
                context['plainte_detail'] = Plainte.objects.get(pk=detail_id)
            except Plainte.DoesNotExist:
                messages.error(request, "La plainte demandée n'existe pas.")
    return render(request, "utilisateur/acc_dcn.html",context)


@login_required
@user_passes_test(is_procureur, login_url='accueil')
def acc_procureur(request):
    mode = request.GET.get('mode')
    detail_id = request.GET.get('detail_id')
    procureur_region = request.user.localite.nom_loc
    context = {
        "user":request.user,
        "po": Plainte.objects.all()
    }
    if mode == 'list':
        # Mode LISTE
        context['plaintes'] = Plainte.objects.filter(
            statut="DISPATCHE", 
            pac_affecte=procureur_region
        )
        
        if detail_id:
            try:
                context['plainte_detail'] = Plainte.objects.get(pk=detail_id)
            except Plainte.DoesNotExist:
                messages.error(request, "La plainte demandée n'existe pas.")
    elif mode == 'RA':
        if detail_id:
            plainte = Plainte.objects.get(pk=detail_id)
            plainte.statut = "COURS"
            plainte.save(update_fields=['statut'])
            nouvel_enregistrement = RegistreArrive(
                date_correspondance=plainte.date_plainte,
                nature='plainte', 
                provenance=f"Plainte en ligne N° {plainte.n_chrono_tkk} - Plaignant : {plainte.ny_mpitory}",
                texte_correspondance=plainte.tranga_kolikoly, 
                observation=f"Auteur présumé : {plainte.ilay_olona_kolikoly}\nLieu/Bureau : {plainte.toorna_birao}",
                statut_traitement="COURS", 
                n_plainte_associe=plainte.n_chrono_tkk,

                utilisateur_creation=request.user 
            )
            
            nouvel_enregistrement.save()
            
    elif mode == 'CSS':
        if detail_id:
            plainte = Plainte.objects.get(pk=detail_id)
            plainte.statut = "CSS"
            plainte.save(update_fields=['statut'])
    return render(request, "utilisateur/acc_proc.html",context)

@login_required
@user_passes_test(is_greffier, login_url='accueil') 
def acc_greffier(request):
    context = {
        'user': request.user,
        'menu_active': 'arrive',
    }
    context['registres'] = RegistreArrive.objects.filter(
             utilisateur_creation__localite=request.user.localite
         ).order_by('-date_arrivee')

    return render(request, 'utilisateur/acc_greffier.html', context)

# VERSION API

# --- AUTHENTIFICATION / INSCRIPTION ---
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
            "role": role, #ut du rôle pour la redirection APK/Frontend Ajo
            "tokken" : csrf_token
        })
    else:
        
        return Response(
            {"detail": "Identifiants invalides."}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

@api_view(['POST'])
def api_logout_view(request):

    logout(request)

    return Response({"detail": "Déconnexion réussie."}, status=status.HTTP_200_OK)

@api_view(['POST'])
def api_inscriptionpub(request):
    form = PublicInscription(request.data)
    if form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                public_group = Group.objects.get(name='public')
                user.groups.add(public_group)
            return Response(
                {"detail": "Inscription réussie.", "user_id": user.id},
                status=status.HTTP_201_CREATED
            )
        except Group.DoesNotExist:
            return Response(
                {"detail": "Erreur: Le groupe 'public' n'existe pas."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_accueil(request):
    user = request.user
    role = 'simple' # Valeur par défaut
    
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
    elif is_dcn(user): # 🔑 Ajout de DCN
        role = 'dcn'

    return Response({"role": role}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_acc_admin(request): 
    """ API pour gérer les différentes listes de l'administrateur (GET). """
    if not is_admin(request.user):
        return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    
    mode = request.GET.get('mode', 'utilisateur') 
    
    data_list = []
    title = ""
    serializer_class = None

    if mode == 'utilisateur':
        title = "LISTE DES UTILISATEURS"
        queryset = Utilisateur.objects.all().select_related('poste', 'localite').prefetch_related('groups')
        serializer_class = UtilisateurSerializer
        
    elif mode == 'groupe':
        title = "LISTE DES GROUPES D'UTILISATEURS"
        queryset = Group.objects.annotate(user_count=Count('utilisateur')) 
        serializer_class = GroupSerializer
        
    elif mode == 'localite':
        title = "LISTE DES LOCALITÉS"
        queryset = Localite.objects.annotate(user_count=Count('utilisateur')) 
        serializer_class = LocaliteSerializer
    
    # 🔑 Ajout du mode 'RA' (Registre Arrivé) pour l'admin, comme dans la vue standard
    elif mode == 'RA':
        title = "REGISTRE D'ARRIVÉE LOCAL"
        # 🔑 Répliquer le filtrage par localité comme dans 'acc_admin' standard
        queryset = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).order_by('-date_arrivee')
        serializer_class = RegistreArriveSerializer # Assurez-vous d'avoir ce serializer
    
    elif mode == 'ajout':
        # Pour le mode 'ajout', on peut renvoyer les informations nécessaires à l'APK pour le formulaire
        # L'ajout POST doit être sur un endpoint séparé (ex: /api/admin/utilisateur/add)
        return Response({
            'detail': 'Endpoint GET pour l\'ajout, fournit juste les metadata.',
            'champs_requis': ['email', 'password', 'nom', 'groupe_id', 'localite_id', 'poste_id', 'matricule'],
            # Renvoyer les options pour les groupes et localités si nécessaire
        }, status=status.HTTP_200_OK)
    
    else:
        return Response(
            {"detail": f"Mode '{mode}' non valide."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Sérialisation finale
    serializer = serializer_class(queryset, many=True)
    return Response({
        'title': title,
        'mode': mode,
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_modifier_utilisateur(request, pk):
    if not is_admin(request.user):
        return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        utilisateur = Utilisateur.objects.get(pk=pk)
    except Utilisateur.DoesNotExist:
        return Response({"detail": "Utilisateur non trouvé."}, status=status.HTTP_404_NOT_FOUND)

    # Ici, nous utilisons un serializer de modification (AdminModificationSerializer)
    # qui doit gérer la mise à jour des champs/groupes.
    serializer = AdminModificationSerializer(utilisateur, data=request.data, partial=True) 
    
    if serializer.is_valid():
        try:
            with transaction.atomic():
                serializer.save()
                # 🔑 Gérer explicitement la modification du groupe si le champ est inclus dans le serializer
                # (Comme dans la vue standard 'modifier_utilisateur' implicitement via le form.save())
            
            return Response({
                "detail": f"L'utilisateur {utilisateur.pk} a été modifié avec succès.",
                "user": UtilisateurSerializer(utilisateur).data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Erreur lors de la modification: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def api_supprimer_utilisateur(request, pk):
    if not is_admin(request.user):
        return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        utilisateur = Utilisateur.objects.get(pk=pk)
    except Utilisateur.DoesNotExist:
        return Response({"detail": "Utilisateur non trouvé."}, status=status.HTTP_404_NOT_FOUND)

   
    if utilisateur.is_superuser:
        return Response(
            {"detail": f"Impossible de supprimer le superutilisateur {utilisateur.email}."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    email_supprime = utilisateur.email
    utilisateur.delete()
    
    return Response(
        {"detail": f"L'utilisateur **{email_supprime}** a été supprimé avec succès."}, 
        status=status.HTTP_200_OK
    )


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def api_public_plaintes(request):
    """ API pour la gestion des plaintes par le Public (List, Add, Modify, Detail Form). """
    if not is_public(request.user):
        return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    
    # Récupération des paramètres pour le mode GET ou la modification POST/PUT
    plainte_id = request.GET.get('plainte_id') or request.data.get('plainte_id')

    # 1. GESTION DE L'AJOUT/MODIFICATION (Méthode POST/PUT)
    if request.method in ['POST', 'PUT']:
        plainte_instance = None
        is_modification = False
        
        # Tentative de récupération pour modification (si plainte_id est fourni)
        if plainte_id:
            try:
                plainte_instance = Plainte.objects.get(pk=plainte_id, utilisateur_creation=request.user)
                is_modification = True
            except Plainte.DoesNotExist:
                return Response({"detail": "Plainte non trouvée ou non autorisée à modifier."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlainteCreationSerializer(
        instance=plainte_instance, 
        data=request.data,
    )
        # serializer = PlainteCreationSerializer(
        #    instance=plainte_instance, 
        #    data=request.data,
        #    files=request.FILES # 🔑 AJOUTER request.FILES ICI pour plus de robustesse
        #)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # 🔑 Injection de l'utilisateur connecté, comme dans la vue standard
                    plainte = serializer.save(
                        utilisateur_creation=(request.user if not is_modification else plainte_instance.utilisateur_creation),
                        utilisateur_modification=request.user
                    )
                
                detail_msg = f'La plainte N° {plainte.n_chrono_tkk} a été modifiée avec succès.' if is_modification else \
                             f"Plainte enregistrée sous le N° {plainte.n_chrono_tkk}."
                
                return Response({
                    "detail": detail_msg,
                    "plainte": PlainteSerializer(plainte).data # Renvoyer l'objet mis à jour
                }, status=status.HTTP_201_CREATED if not is_modification else status.HTTP_200_OK)
            
            except Exception as e:
                return Response({"detail": f"Erreur lors de la sauvegarde: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 2. GESTION DE LA CONSULTATION (Méthode GET)
    else:
        mode = request.GET.get('mode', 'list') 
        detail_id = request.GET.get('detail_id')
        
        if mode == 'list':
            # Filtre
            plaintes = request.user.plaintes_creees.all().order_by('-date_plainte') 
            serializer = PlainteSerializer(plaintes, many=True)
            response_data = {'plaintes': serializer.data}
            
            # detail
            if detail_id:
                try:
                    plainte_detail = Plainte.objects.get(pk=detail_id, utilisateur_creation=request.user)
                    response_data['plainte_detail'] = PlainteSerializer(
                    plainte_detail, 
                    context={'request': request} 
                ).data
                except Plainte.DoesNotExist:
                    response_data['detail_error'] = "La plainte demandée n'existe pas ou n'est pas accessible."
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        elif mode == 'form':
            # Fournir les données nécessaires pour le rendu du formulaire côté APK
            date_actuelle = timezone.now().strftime("%d/%m/%Y")
            prochain_chrono = f"DPL: PROVISOIRE/{timezone.now().year}"
            
            # 
            plainte_instance_data = None
            if plainte_id:
                try:
                    plainte_instance = Plainte.objects.get(pk=plainte_id, utilisateur_creation=request.user)
                    plainte_instance_data = PlainteSerializer(plainte_instance).data
                    prochain_chrono = plainte_instance.n_chrono_tkk # Utiliser le chrono existant
                except Plainte.DoesNotExist:
                    return Response({"detail": "Plainte non trouvée pour modification."}, status=status.HTTP_404_NOT_FOUND)

            return Response({
                "form_title": "Modifier la Plainte" if plainte_id else "Enregistrer une Nouvelle Plainte",
                "n_chrono_tkk": prochain_chrono,
                "date_plainte": date_actuelle,
                "initial_data": plainte_instance_data, # Données de l'instance pour pré-remplissage
                # On pourrait inclure ici les metadata du formulaire (champs, validations)
            }, status=status.HTTP_200_OK)

        return Response(
            {"detail": f"Mode '{mode}' non valide."}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_simple_view(request):
    
    if not is_simple(request.user) and not is_opj(request.user): # Exemple: si simple ET opj peuvent l'utiliser
        return Response({"detail": "Accès non autorisé à l'espace simple."}, status=status.HTTP_403_FORBIDDEN)
    
    mode = request.GET.get('mode', 'list')

    # 1. GESTION DE L'AJOUT (Méthode POST)
    if request.method == 'POST':
        serializer = RegistreArriveSerializer(data=request.data) # Assurez-vous d'avoir ce serializer
        
        if serializer.is_valid():
            try:
               
                registre = serializer.save(utilisateur_creation=request.user) 
                
                return Response({
                    "detail": f"Registre Arrivé **N° {registre.n_enr_arrive}** enregistré avec succès.",
                    "registre": RegistreArriveSerializer(registre).data
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response({"detail": f"Erreur lors de la sauvegarde: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 2. GESTION DE LA CONSULTATION (Méthode GET)
    elif mode == 'list':
        # 🔑 Filtrer par localité, comme dans la vue standard
        registres = RegistreArrive.objects.filter(
             utilisateur_creation__localite=request.user.localite
           ).order_by('-date_arrivee')
        
        serializer = RegistreArriveSerializer(registres, many=True)
        return Response({'registres': serializer.data}, status=status.HTTP_200_OK)
        
    elif mode == 'form':
        # Fournir les données nécessaires pour le rendu du formulaire côté APK
        date_arrivee_systeme = timezone.now().strftime("%Y-%m-%d") 
        
        # 🔑 Répliquer la logique de numérotation provisoire (estimation)
        try:
            last_enr_id = RegistreArrive.objects.aggregate(Max('id'))['id__max']
            next_enr = str((last_enr_id or 0) + 1).zfill(4)
        except Exception:
            next_enr = "0001" 
        
        return Response({
            "n_enr_provisoire": next_enr,
            "date_arrivee_systeme": date_arrivee_systeme,
            # Ajouter les options de champs si nécessaire (ex: types de documents)
        }, status=status.HTTP_200_OK)

    return Response(
        {"detail": f"Mode '{mode}' non valide."}, 
        status=status.HTTP_400_BAD_REQUEST
    )

# --- VUE DCN (Répartition des Plaintes) ---
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_acc_dcn(request):
    """ API pour la gestion des plaintes par le DCN (List, Detail, Dispatch). """
    
    if not is_dcn(request.user):
        return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    
    mode = request.GET.get('mode') or request.data.get('mode')
    
    # 1. GESTION DE LA RÉPARTITION (Méthode POST, mode='dispatch')
    if request.method == 'POST' and mode == 'dispatch':
        plainte_id = request.data.get('idplainte')
        pac_destination = request.data.get('pac') # Le PAC (Pôle d'Action Criminelle) de destination
        
        if not plainte_id or not pac_destination:
             return Response({"detail": "idplainte et pac sont requis pour la répartition."}, status=status.HTTP_400_BAD_REQUEST)
             
        try:
            plainte_a_dispatcher = Plainte.objects.get(pk=plainte_id)
        except Plainte.DoesNotExist:
            return Response({"detail": "Plainte non trouvée."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # 🔑 Logique de répartition (Mise à jour du statut et de la destination)
            plainte_a_dispatcher.statut = "COURS"
            plainte_a_dispatcher.pac_destination = pac_destination # Assurez-vous que ce champ existe sur Plainte
            plainte_a_dispatcher.utilisateur_dispatch = request.user # Ajout de l'utilisateur qui répartit
            plainte_a_dispatcher.save(update_fields=['statut', 'pac_destination', 'utilisateur_dispatch'])
            
            return Response({
                "detail": f"Plainte N° {plainte_a_dispatcher.n_chrono_tkk} répartie vers {pac_destination} avec succès.",
                "plainte": PlainteSerializer(plainte_a_dispatcher).data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"detail": f"Erreur lors de la répartition: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 2. GESTION DE LA CONSULTATION (Méthode GET/POST sans dispatch)
    detail_id = request.GET.get('detail_id')
    
    # 🔑 Liste de TOUTES les plaintes (si DCN voit tout, comme dans la vue standard)
    plaintes = Plainte.objects.all().order_by('-date_plainte')
    
    response_data = {
        "plaintes": PlainteSerializer(plaintes, many=True).data
    }
    
    if detail_id:
        try:
            plainte_detail = Plainte.objects.get(pk=detail_id)
            response_data['plainte_detail'] = PlainteSerializer(plainte_detail).data
        except Plainte.DoesNotExist:
            response_data['detail_error'] = "La plainte demandée n'existe pas."
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST']) 
def plainte_anonyme_api(request):
    """
    Gère la soumission d'une nouvelle plainte anonyme via l'API.
    """
    if request.method == 'POST':
        # Le serializer gère à la fois les données POST et les fichiers (request.FILES)
        serializer = PlainteSerializer(data=request.data) 

        if serializer.is_valid():
            # La méthode .save() appelle la méthode .create() du serializer
            plainte = serializer.save() 
            
            # Personnalisation de la réponse
            response_data = {
                "message": f"Votre plainte a été enregistrée avec succès !",
                # Utiliser le n_chrono généré après la sauvegarde
                "n_chrono_tkk": plainte.n_chrono_tkk, 
                "statut": "enregistré"
            }
            
            # Retourne une réponse avec le statut 201 Created et les données JSON
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        # Si le formulaire n'est pas valide, retourne les erreurs avec le statut 400 Bad Request
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)