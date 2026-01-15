from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token
import base64
from django.db import transaction
from django.urls import reverse
from utilisateur.models import *
from .forms import *
from django.contrib import messages
from .decorators import *
from django.utils import timezone
import qrcode
from io import BytesIO
from utilisateur.models import *
# ----API MODULE  + Ajout de serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    PlainteSerializer, PlainteCreationSerializer
)

#Chargement apres login
@login_required
def accueil(request):
    user = request.user
    if is_admin(user):
        return redirect('utilisateur:acc_admin')
    elif is_procureur(user):
        return redirect('pac:acc_procureur')
    elif is_greffier(user):
        return redirect('pac:acc_greffier')
    elif is_public(user):
        return redirect('pac:public')
    elif is_dcn(user):
        return redirect('pac:dcn')
    if is_opj(user):
        return redirect('pac:acc_opj')
    else :
        return redirect('pac:simple')

#------------------------------------PLAINTE-------------------------------
#Interface choix plaintes
def none(request):
    return render(request, 'pac/none.html')


#-Plainte anonyme
def anonyme(request):
    context = {}
    plainte_instance = None
    context['form_title'] = "Enregistrer une Nouvelle Plainte" 
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
    return render(request, 'pac/anonyme_api.html',context)

#-Plainte public
@login_required
def public(request):
    """ Vue unique qui rend le template HTML en utilisant l'API """
    api_res = api_public_plaintes(request)
    api_data = api_res.data
    mode = request.GET.get('mode', 'list')
    plainte_id = request.GET.get('plainte_id')
    
    context = {
        'mode': mode,
        'plaintes': api_data.get('plaintes'),
        'plainte_detail': api_data.get('plainte_detail'),
        'form_title': api_data.get('form_title'),
        "back_url": reverse('pac:public') + "?mode=list"
    }
    
    if mode == 'form':
        inst = Plainte.objects.filter(pk=plainte_id, utilisateur_creation=request.user).first() if plainte_id else None
        date_actuelle = timezone.now().strftime("%d/%m/%Y")
        prochain_chrono = f"DPL: PROVISOIRE/{timezone.now().year}"
        context['form'] = PlainteForm(instance=inst)
        context['n_chrono_tkk'] = inst.n_chrono_tkk if inst else prochain_chrono
        context['date_plainte'] = inst.date_plainte if inst else date_actuelle
    return render(request, 'pac/acc_public_api.html', context)


#Suppression plainte
@require_POST
def supprimer_plainte(request, plainte_id):
    
    # 1. Récupération de l'objet ou erreur 404
    plainte = get_object_or_404(Plainte, pk=plainte_id)
    plainte_chrono = plainte.n_chrono_tkk # Sauvegarder le chrono avant la suppression
    
    # 2. Suppression de l'objet
    plainte.delete()
    
    # 3. Message de succès et redirection
    messages.success(request, f'La plainte N° {plainte_chrono} a été supprimée avec succès.')
    return redirect('pac:public')

#Detail plainte
def detailp(request):
    context = {}
    # On récupère l'ID depuis la requête (request), pas depuis le modèle (Plainte)
    detp_id = request.GET.get('plainte_id') 
    
    # Optionnel : Récupérer l'objet réel pour l'afficher dans le template
    if detp_id:
        context["plainte_detail"] = Plainte.objects.filter(pk=detp_id).first()
        
    return render(request, "pac/detail_plainte.html", context)
#--API
@api_view(['GET', 'POST', 'DELETE']) # Ajout de DELETE pour tout centraliser
@permission_classes([IsAuthenticated])
def api_public_plaintes(request, plainte_id=None):
    if not is_public(request.user):
        return Response({"detail": "Accès non autorisé."}, status=403)

    # --- LOGIQUE DE SUPPRESSION ---
    if request.method == 'DELETE':
        plainte = get_object_or_404(Plainte, pk=plainte_id, utilisateur_creation=request.user)
        plainte.delete()
        return Response({"detail": "Supprimé avec succès"}, status=200)

    # --- LOGIQUE D'ENREGISTREMENT / MODIFICATION ---
    if request.method == 'POST':
        p_id = request.data.get('plainte_id')
        instance = Plainte.objects.filter(pk=p_id, utilisateur_creation=request.user).first() if p_id else None
        serializer = PlainteCreationSerializer(instance=instance, data=request.data)
        
        if serializer.is_valid():
            plainte = serializer.save(
                utilisateur_creation=(instance.utilisateur_creation if instance else request.user),
                utilisateur_modification=request.user
            )
            msg = "Modifiée avec succès" if instance else "Enregistrée avec succès"
            return Response({"detail": msg}, status=200)
        return Response(serializer.errors, status=400)

    # --- LOGIQUE DE CONSULTATION (GET) ---
    mode = request.GET.get('mode', 'list')
    response_data = {}

    if mode == 'list':
        plaintes = request.user.plaintes_creees.all().order_by('-date_plainte')
        response_data['plaintes'] = PlainteSerializer(plaintes, many=True, context={'request': request}).data
        
        detail_id = request.GET.get('detail_id')
        if detail_id:
            p_detail = Plainte.objects.filter(pk=detail_id, utilisateur_creation=request.user).first()
            if p_detail:
                response_data['plainte_detail'] = PlainteSerializer(p_detail, context={'request': request}).data

    elif mode == 'form':
        plainte_id = request.GET.get('plainte_id')
        response_data['form_title'] = "Modifier la Plainte" if plainte_id else "Nouvelle Plainte"
        

    return Response(response_data)


@api_view(['POST'])
def plainte_anonyme_api(request):
    """
    Gère la soumission d'une plainte anonyme avec génération de QR Code via l'API.
    """
    if request.method == 'POST':
        serializer = PlainteSerializer(data=request.data)

        if serializer.is_valid():
            # 1. Sauvegarde initiale avec commit=False pour modifier les champs
            # Note: Avec DRF, on utilise serializer.save() en passant les arguments
            plainte = serializer.save(
                ny_mpitory="Anonyme",
                est_anonyme=True
            )

            # 2. Préparation des données pour le QR Code
            # On génère l'URL absolue pour le suivi
            url_de_suivi = request.build_absolute_uri(
                reverse('pac:detailp') + f"?plainte_id={plainte.pk}"
            )

            # 3. Génération du QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url_de_suivi)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 4. Encodage en Base64 pour l'envoi via JSON
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # 5. Réponse structurée
            response_data = {
                "message": "Votre plainte a été enregistrée avec succès !",
                "n_chrono_tkk": plainte.n_chrono_tkk,
                "statut": "enregistré",
                "qr_code_base64": qr_code_base64,
                "url_de_suivi": url_de_suivi,
                "mode_anonyme": True
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        # Retourne les erreurs de validation (ex: champs obligatoires manquants)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   

#------------------------------------FIN-PLAINTE-------------------------------

#------------------------------------DCN-------------------------------
@login_required
@user_passes_test(is_dcn, login_url='pac:accueil')
def acc_dcn(request):
    mode = request.GET.get('mode')
    detail_id = request.GET.get('detail_id')
    context = {
        "user":request.user,
        "po": Plainte.objects.all(),
        "back_url": reverse('pac:dcn') + "?mode=list"
    }
    if request.method == 'POST' and mode == 'dispatch':
        plainte_id = request.POST.get('idplainte')
        pac_destination = request.POST.get('pac')
        plainte_a_dispatcher = Plainte.objects.get(pk=plainte_id)

        print(plainte_a_dispatcher)
        plainte_a_dispatcher.statut = "DISPATCHE"
        plainte_a_dispatcher.pac_affecte = pac_destination
        plainte_a_dispatcher.save(update_fields=['statut','pac_affecte'])
        return render(request, "pac/acc_dcn.html",context)
    if mode == 'list':
        # Mode LISTE
        context['plaintes'] = Plainte.objects.all()
        
        if detail_id:
            try:
                context['plainte_detail'] = Plainte.objects.get(pk=detail_id)
            except Plainte.DoesNotExist:
                messages.error(request, "La plainte demandée n'existe pas.")
    return render(request, "pac/acc_dcn.html",context)

#------------------------------------FIN-DCN-------------------------------

#------------------------------------PROCUREUR-------------------------------
@login_required
@user_passes_test(is_procureur, login_url='pac:accueil')
def acc_procureur(request):
    mode = request.GET.get('mode')
    plainte_id = request.GET.get('detail_id')
    procureur_region = request.user.localite.nom_loc
    context = {
        "user":request.user,
        "po": Plainte.objects.all(),
        "back_url": reverse('pac:procureur') + "?mode=list"
    }
    if mode == 'list':
        # Mode LISTE
        context['plaintes'] = Plainte.objects.filter(
            statut="DISPATCHE", 
            pac_affecte=procureur_region
        )
        
        if plainte_id:
            try:
                context['plainte_detail'] = Plainte.objects.get(pk=plainte_id)
            except Plainte.DoesNotExist:
                messages.error(request, "La plainte demandée n'existe pas.")
    
            
    if request.method == "POST":
        plainte_id= request.POST.get("idplainte")
        observations = request.POST.get("observation")
        mode = request.POST.get("mode")
        
        if mode == "css":
            plainte = Plainte.objects.get(pk=plainte_id)
            plainte.statut = "CSS"
            plainte.observation = observations
            plainte.save(update_fields=['statut','observation'])
        else :
            plainte = Plainte.objects.get(pk=plainte_id)
            plainte.statut = "COURS"
            plainte.observation = observations
            plainte.save(update_fields=['statut','observation'])
            nouvel_enregistrement = RegistreArrive(
                date_correspondance=plainte.date_plainte,
                nature='plainte', 
                provenance=f"Plainte en ligne N° {plainte.n_chrono_tkk} - Plaignant : {plainte.ny_mpitory} - Procureur",
                texte_correspondance=plainte.tranga_kolikoly, 
                observation=observations,
                statut_traitement="COURS", 
                n_plainte_associe=plainte.n_chrono_tkk,

                utilisateur_creation=request.user 
            )
            
            nouvel_enregistrement.save()
        
    return render(request, "pac/acc_proc.html",context)

