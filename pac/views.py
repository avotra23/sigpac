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
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
import qrcode
from io import BytesIO
from utilisateur.models import *
from django.http import JsonResponse
# ----API MODULE  + Ajout de serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    PlainteSerializer, PlainteCreationSerializer, OPJCreationSerializer,OPJSerializer
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
        return redirect('pac:greffier')
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
def index_choix(request):
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
        "back_url": reverse('pac:public') + "?mode=list",
        "groups" : "public",
    }
    
    if mode == 'form':
        inst = Plainte.objects.filter(pk=plainte_id, utilisateur_creation=request.user).first() if plainte_id else None
        date_actuelle = timezone.now().strftime("%d/%m/%Y")
        prochain_chrono = f"DPL: PROVISOIRE/{timezone.now().year}"
        context['form'] = PlainteForm(instance=inst)
        context['n_chrono_tkk'] = inst.n_chrono_tkk if inst else prochain_chrono
        context['date_plainte'] = inst.date_plainte if inst else date_actuelle
    return render(request, 'pac/acc_public_api.html', context)

#-Plainte OPJ
@login_required
def opj_list_view(request):
    """ Rend le template HTML pour les dossiers OPJ """
    api_res = api_opj_views(request)
    api_data = api_res.data
    mode = request.GET.get('mode', 'list')
    opj_id = request.GET.get('opj_id')
    
    context = {
        'mode': mode,
        'dossiers': api_data.get('dossiers'),
        'opj_detail': api_data.get('opj_detail'),
        'form_title': api_data.get('form_title'),
        "back_url": reverse('pac:opj'),
        "groups":"opj",
    }
    
    if mode == 'form':
        instance = OPJ.objects.filter(pk=opj_id, utilisateur_creation=request.user).first() if opj_id else None
        date_actuelle = timezone.now().strftime("%d/%m/%Y")
        prochain_chrono = f"DPSA: PROVISOIRE/{timezone.now().year}"
        
        context['form'] = OPJForm(instance=instance)
        context['n_chrono_opj'] = instance.n_chrono_opj if instance else prochain_chrono
        context['date_plainte'] = instance.date_plainte if instance else date_actuelle
        
    return render(request, 'pac/acc_opj_api.html', context)

# 2. API Centralisée pour OPJ
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_opj_views(request, pk=None):
    # Logique de suppression
    if request.method == 'DELETE':
        dossier = get_object_or_404(OPJ, pk=pk, utilisateur_creation=request.user)
        dossier.delete()
        return Response({"detail": "Dossier supprimé avec succès"}, status=200)

    # Logique de création / modification
    if request.method == 'POST':
        opj_id = request.data.get('opj_id')
        instance = OPJ.objects.filter(pk=opj_id, utilisateur_creation=request.user).first() if opj_id else None
        serializer = OPJCreationSerializer(instance=instance, data=request.data)
        
        if serializer.is_valid():
            # Génération du chrono si nouveau dossier
            chrono = instance.n_chrono_opj if instance else f"DPSA:{timezone.now().year}/OPJ"
            
            serializer.save(
                utilisateur_creation=(instance.utilisateur_creation if instance else request.user),
                utilisateur_modification=request.user,
                statut = 'DISPATCHE',
                pac_affecte='ANTANANARIVO',  
            )
            msg = "Dossier mis à jour" if instance else "Dossier enregistré avec succès"
            return Response({"detail": msg}, status=200)
        return Response(serializer.errors, status=400)

    # Logique GET (Liste et Détails)
    mode = request.GET.get('mode', 'list')
    response_data = {}

    if mode == 'list':
        # Utilise le nouveau related_name 'opj_crees' définit précédemment
        qs = request.user.opj_crees.all().order_by('-date_plainte')
        response_data['dossiers'] = OPJSerializer(qs, many=True).data
        
        detail_id = request.GET.get('detail_id')
        if detail_id:
            d_detail = OPJ.objects.filter(pk=detail_id, utilisateur_creation=request.user).first()
            if d_detail:
                response_data['opj_detail'] = OPJSerializer(d_detail).data

    elif mode == 'form':
        opj_id = request.GET.get('opj_id')
        response_data['form_title'] = "Modifier le Dossier" if opj_id else "Nouveau Dossier OPJ"

    return Response(response_data)

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
      
        p_id = plainte_id or request.data.get('plainte_id') or request.data.get('id')
        
        instance = Plainte.objects.filter(pk=p_id, utilisateur_creation=request.user).first() if p_id else None
        
        
        serializer = PlainteCreationSerializer(instance=instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            
            plainte = serializer.save(
                utilisateur_creation=(instance.utilisateur_creation if instance else request.user),
                utilisateur_modification=request.user
            )
            msg = "Modifiée avec succès" if instance else "Enregistrée avec succès"
            return Response({"detail": msg, "id": plainte.id}, status=200)
        
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
    mode = request.GET.get('mode', 'list')
    detail_id = request.GET.get('detail_id')
    search_query = request.GET.get('search', '')
    tribunal_filtre = request.GET.get('tribunal')
    statute = request.GET.get('statut')
    
    stats_tribunaux = []
    
    # 1. Traitement du Dispatch (POST)
    if request.method == 'POST' and mode == 'dispatch':
        plainte_id = request.POST.get('idplainte')
        pac_destination = request.POST.get('pac')
        plainte_a_dispatcher = get_object_or_404(Plainte, pk=plainte_id)
        plainte_a_dispatcher.statut = "DISPATCHE"
        plainte_a_dispatcher.pac_affecte = pac_destination
        plainte_a_dispatcher.save(update_fields=['statut', 'pac_affecte'])
        messages.success(request, f"La plainte a été dispatchée vers le PAC {pac_destination}")
        mode = 'list' # Retour à la liste après dispatch

    # 2. Calcul des Statistiques (Toujours calculées pour éviter les erreurs de graphiques)
    for code, label in Plainte.LOCALITE_CHOICES:
        qs_en_ligne = Plainte.objects.filter(pac_affecte=code)
        qs_opj = OPJ.objects.filter(pac_affecte=code)
        
        stats_tribunaux.append({
            'code': code,
            'nom': label,
            'nb_entree': qs_en_ligne.count() + qs_opj.count(),
            'nb_sortie': qs_en_ligne.filter(statut='TRAITEE').count() + qs_opj.filter(statut='TRAITEE').count(),
            'nb_en_cours': qs_en_ligne.filter(statut__in=['DISPATCHE', 'COURS']).count() + qs_opj.filter(statut__in=['DISPATCHE', 'COURS']).count(),
            'nb_css': qs_en_ligne.filter(statut='CSS').count() + qs_opj.filter(statut='CSS').count(),
        })

    # 3. Préparation de la QuerySet principale (Filtrage et Recherche)
    if tribunal_filtre:
        plaintes_qs = Plainte.objects.filter(pac_affecte=tribunal_filtre).order_by('-date_plainte')
        if statute:
            plaintes_qs = plaintes_qs.filter(statut=statute)
    else:
        plaintes_qs = Plainte.objects.all().order_by('-date_plainte')

    if search_query:
        plaintes_qs = plaintes_qs.filter(
            Q(n_chrono_tkk__icontains=search_query) |
            Q(ilay_olona_kolikoly__icontains=search_query) |
            Q(tranga_kolikoly__icontains=search_query)
        )

    # 4. Pagination
    paginator = Paginator(plaintes_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Construction du Contexte FINAL
    context = {
        "user": request.user,
        "po": page_obj,
        "search_query": search_query,
        "back_url": reverse('pac:dcn'),
        "groups": "dcn",
        "stats_tribunaux": stats_tribunaux,
        # IMPORTANT : On force 'arrive' pour que le tableau soit visible en mode liste
        "menu_active": mode if mode in ['trib', 'stat'] else "arrive",
        "titre_menu": "Plaintes en ligne"
    }

    # Ajustements spécifiques selon le mode
    if mode == 'list' and detail_id:
        context['plainte_detail'] = get_object_or_404(Plainte, pk=detail_id)

    elif mode == 'trib':
        context["titre_menu"] = "Les Tribunaux traitants au sein du PAC"

    elif mode == 'stat':
        context["titre_menu"] = "Tableau de Bord National"
        # KPI Globaux
        traitees = Plainte.objects.filter(statut='TRAITEE').count() + OPJ.objects.filter(statut='TRAITEE').count()
        total_g = Plainte.objects.count() + OPJ.objects.count()
        
        context['kpi'] = {
            'total': total_g,
            'traitées': traitees,
            'attente': Plainte.objects.filter(statut='ATTENTE').count(),
            'en_cours': (Plainte.objects.filter(statut__in=['DISPATCHE', 'COURS']).count() + OPJ.objects.filter(statut__in=['DISPATCHE', 'COURS']).count()),
            'css': Plainte.objects.filter(statut='CSS').count() + OPJ.objects.filter(statut='CSS').count(),
            'taux': round((traitees / total_g * 100), 1) if total_g > 0 else 0
        }
        context['labels_pac'] = [s['nom'] for s in stats_tribunaux]
        context['data_pac'] = [s['nb_entree'] for s in stats_tribunaux]

    if tribunal_filtre:
        context['titre_menu'] = f"Plaintes affectées à : {tribunal_filtre}"

    return render(request, "pac/acc_dcn.html", context)
# API DCN 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dcn_plaintes(request):
    # 1. Vérification du rôle
    if not is_dcn(request.user):
        return Response({"detail": "Accès non autorisé."}, status=403)

    mode = request.GET.get('mode', 'list')
    detail_id = request.GET.get('detail_id')
    
    # Structure de base de la réponse
    response_data = {
        "groups": "dcn",
        "menu_active": mode if mode in ['trib', 'stat'] else "arrive",
        "titre_menu": "Plainte en ligne"
    }

    # --- LOGIQUE STATISTIQUE (Commune à 'trib' et 'stat') ---
    if mode in ['trib', 'stat']:
        stats_tribunaux = []
        for code, label in Plainte.LOCALITE_CHOICES:
            qs_en_ligne = Plainte.objects.filter(pac_affecte=code)
            qs_opj = OPJ.objects.filter(pac_affecte=code)
            
            stats_tribunaux.append({
                'code': code,
                'nom': label,
                'nb_entree': qs_en_ligne.count() + qs_opj.count(),
                'nb_sortie': qs_en_ligne.filter(statut='TRAITEE').count() + qs_opj.filter(statut='TRAITEE').count(),
                'nb_en_cours': (qs_en_ligne.filter(statut__in=['DISPATCHE', 'COURS']).count() + 
                               qs_opj.filter(statut__in=['DISPATCHE', 'COURS']).count()),
                'nb_css': qs_en_ligne.filter(statut='CSS').count() + qs_opj.filter(statut='CSS').count(),
            })
        response_data['stats_tribunaux'] = stats_tribunaux

    # --- MODE STATISTIQUES (KPI & Graphiques) ---
    if mode == 'stat':
        response_data['titre_menu'] = "Tableau de Bord National"
        
        # Calcul des KPI globaux
        total_p = Plainte.objects.count()
        total_o = OPJ.objects.count()
        total_g = total_p + total_o
        traitees = Plainte.objects.filter(statut='TRAITEE').count() + OPJ.objects.filter(statut='TRAITEE').count()
        
        response_data['kpi'] = {
            'total': total_g,
            'traitées': traitees,
            'attente': Plainte.objects.filter(statut='ATTENTE').count(),
            'en_cours': (Plainte.objects.filter(statut__in=['DISPATCHE', 'COURS']).count() + 
                        OPJ.objects.filter(statut__in=['DISPATCHE', 'COURS']).count()),
            'css': Plainte.objects.filter(statut='CSS').count() + OPJ.objects.filter(statut='CSS').count(),
            'taux': round((traitees / total_g * 100), 1) if total_g > 0 else 0
        }
        # Données formatées pour les graphiques (Labels et Data)
        response_data['labels_pac'] = [s['nom'] for s in response_data['stats_tribunaux']]
        response_data['data_pac'] = [s['nb_entree'] for s in response_data['stats_tribunaux']]

    # --- MODE LISTE OU TRIBUNAL ---
    elif mode == 'trib':
        response_data['titre_menu'] = "Les Tribunaux traitants au sein du PAC"
    
    else: # Mode 'list' par défaut
        plaintes = Plainte.objects.all().order_by('-date_plainte')
        response_data['plaintes'] = PlainteSerializer(plaintes, many=True).data
        
        if detail_id:
            plainte_detail = Plainte.objects.filter(pk=detail_id).first()
            if plainte_detail:
                response_data['plainte_detail'] = PlainteSerializer(plainte_detail).data

    return Response(response_data)
#------------------------------------FIN-DCN-------------------------------

#------------------------------------PROCUREUR-------------------------------

@login_required
@user_passes_test(is_procureur, login_url='pac:accueil')
def acc_procureur(request):
    # On récupère le mode actuel. 'arrive' est le mode par défaut pour "Plainte en ligne"
    mode = request.GET.get('mode', 'arrive') 
    detail_id = request.GET.get('detail_id')
    procureur_region = request.user.localite.nom_loc
    search_query = request.GET.get('search', '')

    context = {
        "user": request.user,
        "back_url": reverse('pac:procureur'),
        "groups": "procureur",
        "mode_actuel": mode, # Utile pour les formulaires dans le template
    }

    # --- 1. LOGIQUE DE TRAITEMENT (POST) ---
    if request.method == "POST":
        obj_id = request.POST.get("idplainte")
        observations = request.POST.get("observation")
        action = request.POST.get("mode")  # 'ra' ou 'css'
        target_model = request.POST.get("target_model")
        
        # On récupère le mode de navigation pour rediriger au bon endroit après le POST
        nav_mode = request.POST.get("nav_mode", mode)

        ModelClass = OPJ if target_model == "OPJ" else Plainte
        obj = get_object_or_404(ModelClass, pk=obj_id)

        with transaction.atomic():
            ancien_statut = obj.statut 

            if action == "css":
                obj.statut = "CSS"
                messages.warning(request, f"Dossier {obj_id} classé sans suite.")
            else:
                obj.statut = "COURS"
                ref = obj.n_chrono_opj if target_model == "OPJ" else obj.n_chrono_tkk
                
                if ancien_statut == "CSS":
                    source_label = f"RETRAITEMENT (Ex-CSS) - N° {ref}"
                else:
                    source_label = f"Source {target_model} N° {ref}"

                RegistreArrive.objects.create(
                    plainte_origine=obj if target_model != "OPJ" else None,
                    n_chrono_opj=obj.n_chrono_opj if target_model == "OPJ" else None,
                    nbe_dossier=obj.n_chrono_tkk if target_model != "OPJ" else None,
                    date_correspondance=timezone.now().date(),
                    nature='opj' if target_model == "OPJ" else 'plainte',
                    expediteur=source_label,
                    objet_demande=getattr(obj, 'tranga_kolikoly', 'Dossier transmis'),
                    observation=observations,
                    statut_traitement="COURS",
                    utilisateur_creation=request.user 
                )
                messages.success(request, f"Dossier {ref} renvoyé au greffe.")

            obj.observation = observations
            obj.save()
            
        # Redirection en gardant le mode de navigation
        return redirect(f"{request.path}?mode={nav_mode}")

    # --- 2. LOGIQUE DE NAVIGATION (GET) ---
    
    if mode == 'ListeOPJ':
        po_queryset = OPJ.objects.filter(pac_affecte=procureur_region, statut="DISPATCHE")
        titre = "Plaintes OPJ"
        menu = "OPJ"
        is_ra = False
    elif mode == 'ListeCSS':
        po_queryset = Plainte.objects.filter(pac_affecte=procureur_region, statut="CSS")
        titre = "Dossiers Classés Sans Suite (CSS)"
        menu = "CSS"
        is_ra = False
    elif mode == 'ListeRA':
        po_queryset = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite, 
            statut_traitement="COURS"
        ).order_by('-date_arrivee')
        titre = "Dossiers au Registre d'Arrivée (Greffe)"
        menu = "RA"
        is_ra = True
    else: # Mode 'arrive' (Plainte en ligne)
        po_queryset = Plainte.objects.filter(pac_affecte=procureur_region, statut="DISPATCHE")
        titre = "Plaintes en ligne"
        menu = "arrive"
        is_ra = False

    # Application de la recherche commune
    if search_query:
        if mode == 'ListeRA':
            po_queryset = po_queryset.filter(
                Q(expediteur__icontains=search_query) | 
                Q(observation__icontains=search_query)
            )
        elif mode == 'ListeOPJ':
            po_queryset = po_queryset.filter(
                Q(n_chrono_opj__icontains=search_query) |
                Q(ny_mpitory__icontains=search_query) |
                Q(ilay_olona_kolikoly__icontains=search_query)
            )
        else: # Plainte ou CSS
            po_queryset = po_queryset.filter(
                Q(n_chrono_tkk__icontains=search_query) |
                Q(ny_mpitory__icontains=search_query) |
                Q(ilay_olona_kolikoly__icontains=search_query)
            )

    # Pagination
    paginator = Paginator(po_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context.update({
        "titre_menu": titre,
        "menu_active": menu,
        "po": page_obj,
        "search_query": search_query,
        "is_ra": is_ra,
    })

    # --- 3. GESTION DES DÉTAILS ---
    if detail_id:
        if mode == 'ListeRA':
            reg = get_object_or_404(RegistreArrive, pk=detail_id)
            if reg.plainte_origine:
                context['plainte_detail'] = reg.plainte_origine
            elif reg.n_chrono_opj:
                context['opj_detail'] = OPJ.objects.filter(n_chrono_opj=reg.n_chrono_opj).first()
        elif mode == 'ListeOPJ':
            context['opj_detail'] = get_object_or_404(OPJ, pk=detail_id)
        else:
            context['plainte_detail'] = get_object_or_404(Plainte, pk=detail_id)

    return render(request, "pac/acc_proc.html", context)#------------------------------------FIN PROCUREUR-----------------------------


#------------------------------------GREFFIER-----------------------------
@login_required
@user_passes_test(is_greffier, login_url='accueil')
def acc_greffier(request):

    # ── 1. PARAMÈTRES ────────────────────────────────────────────────────────
    # Lire 'mode' depuis POST (AJAX) ou GET (navigation)
    if request.method == 'POST':
        mode = request.POST.get('mode', request.GET.get('mode', 'list'))
    else:
        mode = request.GET.get('mode', 'list')

    reg_type      = request.GET.get('type', 'pre_ra')
    detail_id     = request.GET.get('detail_id')
    validation_id = request.GET.get('valider_id')
    ra_id         = request.GET.get('ra_id')
    target_type   = request.GET.get('target_type')
    search_query  = request.GET.get('search', '')
    page_number   = request.GET.get('page', 1)

    context = {
        'user': request.user,
        'groups': "greffier",
        'mode': mode,
        'reg_type': reg_type,
        'search_query': search_query,
        'date_arrivee_systeme': timezone.now().strftime("%Y-%m-%d"),
    }

    # ════════════════════════════════════════════════════════════════════════
    #  2. HANDLERS POST AJAX
    # ════════════════════════════════════════════════════════════════════════

    # ── SAVE ST ──────────────────────────────────────────────────────────────
    if request.method == 'POST' and mode == 'save_st':
        try:
            with transaction.atomic():
                st_id      = request.POST.get('st_id')
                ra_id_post = request.POST.get('ra_id')
                ra_source  = get_object_or_404(RegistreArrive, pk=ra_id_post)
                if st_id:
                    st_obj  = get_object_or_404(RegistreST, pk=st_id)
                    message = "Dossier ST mis à jour"
                else:
                    st_obj  = RegistreST(registre_arrive=ra_source, utilisateur_creation=request.user)
                    message = "Dossier enregistré au ST avec succès"
                st_obj.date_st      = request.POST.get('date_st')
                st_obj.objet        = request.POST.get('objet')
                st_obj.destinataire = request.POST.get('destinataire')
                st_obj.observation  = request.POST.get('observation')
                st_obj.rappel       = request.POST.get('rappel')
                st_obj.resultat     = request.POST.get('resultat')
                st_obj.save()
                return JsonResponse({'status': 'success', 'message': message})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ── SAVE CSCA ─────────────────────────────────────────────────────────────
    if request.method == 'POST' and mode == 'save_csca':
        try:
            with transaction.atomic():
                csca_id    = request.POST.get('csca_id')
                ra_id_post = request.POST.get('ra_id')
                ra_source  = get_object_or_404(RegistreArrive, pk=ra_id_post)
                if csca_id:
                    csca_obj = get_object_or_404(RegistreCSCA, pk=csca_id)
                    message  = f"Dossier CSCA N° {csca_obj.n_chrono} mis à jour"
                else:
                    csca_obj = RegistreCSCA(registre_arrive=ra_source, utilisateur_creation=request.user)
                    message  = "Nouveau dossier CSCA enregistré"
                csca_obj.date_csca              = request.POST.get('date_csca')
                csca_obj.demandeur              = request.POST.get('demandeur')
                csca_obj.entite                 = request.POST.get('entite')
                csca_obj.objet                  = request.POST.get('objet')
                csca_obj.intitule               = request.POST.get('intitule')
                csca_obj.requisitoire_mp        = request.POST.get('requisitoire_mp')
                csca_obj.decision               = request.POST.get('decision')
                csca_obj.transmission_president = request.POST.get('transmission_president')
                csca_obj.appel                  = request.POST.get('appel')
                csca_obj.resultat_appel         = request.POST.get('resultat_appel')
                csca_obj.save()
                return JsonResponse({'status': 'success', 'message': message})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ── SAVE RP ───────────────────────────────────────────────────────────────
    if request.method == 'POST' and mode == 'save_rp':
        try:
            with transaction.atomic():
                rp_id   = request.POST.get('rp_id')
                ra_id_p = request.POST.get('ra_id')
                is_new  = not bool(rp_id)
                rp_obj  = get_object_or_404(RegistreRP, pk=rp_id) if rp_id else RegistreRP(utilisateur_creation=request.user)
                if ra_id_p:
                    rp_obj.registre_arrive = get_object_or_404(RegistreArrive, pk=ra_id_p)
                elif not ra_id_p and not is_new:
                    rp_obj.registre_arrive = None
                rp_obj.date_entree          = request.POST.get('date_entree') or None
                rp_obj.n_be_opj             = request.POST.get('n_be_opj', '')
                rp_obj.plaignant            = request.POST.get('plaignant', '')
                rp_obj.infraction           = request.POST.get('infraction', '')
                rp_obj.date_infraction      = request.POST.get('date_infraction') or None
                rp_obj.montant              = request.POST.get('montant', '')
                rp_obj.date_mandat_depot    = request.POST.get('date_mandat_depot') or None
                rp_obj.css                  = request.POST.get('css', '')
                rp_obj.observation          = request.POST.get('observation', '')
                rp_obj.ref_appel            = request.POST.get('ref_appel', '')
                rp_obj.ref_juge_instruction = request.POST.get('ref_juge_instruction', '')
                rp_obj.save()
                return JsonResponse({
                    'status':    'success',
                    'message':   f"Dossier RP {'créé' if is_new else 'mis à jour'} — N° {rp_obj.numero_rp}",
                    'rp_id':     rp_obj.pk,
                    'numero_rp': rp_obj.numero_rp,
                    'is_new':    is_new,
                })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ── SAVE / DELETE PERSONNE MORALE RP ──────────────────────────────────────
    if request.method == 'POST' and mode == 'save_pm_rp':
        try:
            with transaction.atomic():
                rp_obj = get_object_or_404(RegistreRP, pk=request.POST.get('rp_id'))
                pm_id  = request.POST.get('pm_id')
                pm_obj = get_object_or_404(PersonneMoraleRP, pk=pm_id, registre_rp=rp_obj) if pm_id else PersonneMoraleRP(registre_rp=rp_obj)
                pm_obj.raison_sociale  = request.POST.get('raison_sociale', '')
                pm_obj.forme_juridique = request.POST.get('forme_juridique', '')
                pm_obj.activite        = request.POST.get('activite', '')
                pm_obj.save()
                return JsonResponse({'status': 'success', 'message': "Personne morale enregistrée", 'pm_id': pm_obj.pk})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST' and mode == 'delete_pm_rp':
        try:
            get_object_or_404(PersonneMoraleRP, pk=request.POST.get('pm_id')).delete()
            return JsonResponse({'status': 'success', 'message': "Personne morale supprimée"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ── SAVE / DELETE PERSONNE PHYSIQUE RP ────────────────────────────────────
    if request.method == 'POST' and mode == 'save_pp_rp':
        try:
            with transaction.atomic():
                rp_obj = get_object_or_404(RegistreRP, pk=request.POST.get('rp_id'))
                pp_id  = request.POST.get('pp_id')
                pp_obj = get_object_or_404(PersonnePhysiqueRP, pk=pp_id, registre_rp=rp_obj) if pp_id else PersonnePhysiqueRP(registre_rp=rp_obj)
                pp_obj.type_personne  = request.POST.get('type_personne', 'prevenu')
                pp_obj.numero_prevenu = request.POST.get('numero_prevenu', '')
                pp_obj.nom            = request.POST.get('nom', '')
                pp_obj.prenom         = request.POST.get('prenom', '')
                pp_obj.age            = request.POST.get('age') or None
                pp_obj.nationalite    = request.POST.get('nationalite', '')
                pp_obj.genre          = request.POST.get('genre', '')
                pp_obj.fonction       = request.POST.get('fonction', '')
                pp_obj.save()
                return JsonResponse({'status': 'success', 'message': "Personne physique enregistrée", 'pp_id': pp_obj.pk})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST' and mode == 'delete_pp_rp':
        try:
            get_object_or_404(PersonnePhysiqueRP, pk=request.POST.get('pp_id')).delete()
            return JsonResponse({'status': 'success', 'message': "Personne supprimée"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ── SAVE AUTRES MENU RP ───────────────────────────────────────────────────
    if request.method == 'POST' and mode == 'save_autres_rp':
        try:
            with transaction.atomic():
                rp_obj    = get_object_or_404(RegistreRP, pk=request.POST.get('rp_id'))
                am_obj, _ = AutresMenuRP.objects.get_or_create(registre_rp=rp_obj)
                am_obj.mandat_arret         = request.POST.get('mandat_arret', '')
                am_obj.annee                = request.POST.get('annee', '')
                am_obj.citation_directe     = request.POST.get('citation_directe', '')
                am_obj.renvoi_audience      = request.POST.get('renvoi_audience', '')
                am_obj.requisitoire_informe = request.POST.get('requisitoire_informe', '')
                am_obj.renvoi_cco           = request.POST.get('renvoi_cco', '')
                am_obj.save()
                return JsonResponse({'status': 'success', 'message': "Autres menu enregistré"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST' and mode == 'delete_rp':
        try:
            get_object_or_404(RegistreRP, pk=request.POST.get('rp_id')).delete()
            return JsonResponse({'status': 'success', 'message': "Dossier RP supprimé"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ════════════════════════════════════════════════════════════════════════
    #  SAVE / DELETE CCO  ← NOUVEAU
    # ════════════════════════════════════════════════════════════════════════
    if request.method == 'POST' and mode == 'save_cco':
        try:
            with transaction.atomic():
                cco_id  = request.POST.get('cco_id')
                ra_id_p = request.POST.get('ra_id')
                is_new  = not bool(cco_id)
                cco_obj = get_object_or_404(RegistreCCO, pk=cco_id) if cco_id else RegistreCCO(utilisateur_creation=request.user)
                if ra_id_p:
                    cco_obj.registre_arrive = get_object_or_404(RegistreArrive, pk=ra_id_p)
                elif not is_new:
                    cco_obj.registre_arrive = None
                cco_obj.date_cco             = request.POST.get('date_cco') or None
                cco_obj.n_chrono_st          = request.POST.get('n_chrono_st', '')
                cco_obj.n_dossier            = request.POST.get('n_dossier', '')
                cco_obj.requisitoire_parquet = request.POST.get('requisitoire_parquet', '')
                cco_obj.objet                = request.POST.get('objet', '')
                cco_obj.n_be_cco             = request.POST.get('n_be_cco', '')
                cco_obj.save()
                return JsonResponse({
                    'status':   'success',
                    'message':  f"CCO {'créé' if is_new else 'mis à jour'} — N° {cco_obj.n_chrono}",
                    'cco_id':   cco_obj.pk,
                    'n_chrono': cco_obj.n_chrono,
                    'is_new':   is_new,
                })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST' and mode == 'delete_cco':
        try:
            get_object_or_404(RegistreCCO, pk=request.POST.get('cco_id')).delete()
            return JsonResponse({'status': 'success', 'message': "Dossier CCO supprimé"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ════════════════════════════════════════════════════════════════════════
    #  SAVE / DELETE APPEL  ← NOUVEAU
    # ════════════════════════════════════════════════════════════════════════
    if request.method == 'POST' and mode == 'save_appel':
        try:
            with transaction.atomic():
                appel_id  = request.POST.get('appel_id')
                ra_id_p   = request.POST.get('ra_id')
                is_new    = not bool(appel_id)

                appel_obj = get_object_or_404(RegistreAppel, pk=appel_id) if appel_id \
                            else RegistreAppel(utilisateur_creation=request.user)

                if ra_id_p:
                    appel_obj.registre_arrive = get_object_or_404(RegistreArrive, pk=ra_id_p)
                elif not is_new:
                    appel_obj.registre_arrive = None

                appel_obj.date_appel           = request.POST.get('date_appel') or None
                appel_obj.n_rp                 = request.POST.get('n_rp', '')
                appel_obj.ref_juge_instruction = request.POST.get('ref_juge_instruction', '')
                appel_obj.resume_affaire       = request.POST.get('resume_affaire', '')
                appel_obj.inculpation          = request.POST.get('inculpation', '')
                appel_obj.declaration_appel    = request.POST.get('declaration_appel', '')
                appel_obj.n_be_appel           = request.POST.get('n_be_appel', '')
                appel_obj.save()

                # ── Remonter jusqu'à la source et passer en TRAITEE ──────────
                source_maj = None   # objet Plainte ou OPJ mis à jour
                source_type = None  # 'plainte' ou 'opj'

                if appel_obj.registre_arrive:
                    ra = appel_obj.registre_arrive

                    if ra.nature == 'opj' and ra.n_chrono_opj:
                        opj = OPJ.objects.filter(n_chrono_opj=ra.n_chrono_opj).first()
                        if opj and opj.statut != 'TRAITEE':
                            opj.statut = 'TRAITEE'
                            opj.save(update_fields=['statut'])
                            source_maj  = opj
                            source_type = 'opj'

                    elif ra.plainte_origine:
                        plainte = ra.plainte_origine
                        if plainte.statut != 'TRAITEE':
                            plainte.statut = 'TRAITEE'
                            plainte.save(update_fields=['statut'])
                            source_maj  = plainte
                            source_type = 'plainte'

                    elif ra.nbe_dossier:
                        plainte = Plainte.objects.filter(n_chrono_tkk=ra.nbe_dossier).first()
                        if plainte and plainte.statut != 'TRAITEE':
                            plainte.statut = 'TRAITEE'
                            plainte.save(update_fields=['statut'])
                            source_maj  = plainte
                            source_type = 'plainte'

                # ── Message de retour ─────────────────────────────────────────
                message = (
                    f"Appel {'créé' if is_new else 'mis à jour'} — N° {appel_obj.n_chrono_appel}"
                )
                if source_maj:
                    ref = (
                        source_maj.n_chrono_opj if source_type == 'opj'
                        else source_maj.n_chrono_tkk
                    )
                    message += f" | Dossier source {ref} marqué TRAITÉE ✔"

                return JsonResponse({
                    'status':         'success',
                    'message':        message,
                    'appel_id':       appel_obj.pk,
                    'n_chrono_appel': appel_obj.n_chrono_appel,
                    'is_new':         is_new,
                    'source_traitee': bool(source_maj),
                })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST' and mode == 'delete_appel':
        try:
            get_object_or_404(RegistreAppel, pk=request.POST.get('appel_id')).delete()
            return JsonResponse({'status': 'success', 'message': "Dossier Appel supprimé"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # ════════════════════════════════════════════════════════════════════════
    #  3. VALIDATION N° RA
    # ════════════════════════════════════════════════════════════════════════
    if validation_id:
        registre = get_object_or_404(
            RegistreArrive,
            pk=validation_id,
            utilisateur_creation__localite=request.user.localite
        )
        n_ra = registre.attribuer_ra()
        messages.success(request, f"Validé avec le N° : {n_ra}")
        return redirect('pac:greffier')

    # ════════════════════════════════════════════════════════════════════════
    #  4. LOGIQUE DÉTAILS  (reg_type détermine l'objet affiché)
    # ════════════════════════════════════════════════════════════════════════
    if detail_id:
        context['mode']     = 'detail'
        context['reg_type'] = reg_type

        if reg_type == 'st':
            st_obj = get_object_or_404(
                RegistreST.objects.select_related('registre_arrive', 'utilisateur_creation'),
                pk=detail_id
            )
            ra = st_obj.registre_arrive
            context.update({
                'reg_detail':    st_obj,
                'ra_source':     ra,
                'is_st': True, 'is_csca': False, 'is_cco': False, 'is_appel': False,
                'csca_associe':  RegistreCSCA.objects.filter(registre_arrive=ra).first()  if ra else None,
                'cco_associe':   RegistreCCO.objects.filter(registre_arrive=ra).first()   if ra else None,
                'appel_associe': RegistreAppel.objects.filter(registre_arrive=ra).first() if ra else None,
            })

        elif reg_type == 'csca':
            csca_obj = get_object_or_404(
                RegistreCSCA.objects.select_related('registre_arrive', 'utilisateur_creation'),
                pk=detail_id
            )
            ra = csca_obj.registre_arrive
            context.update({
                'reg_detail':    csca_obj,
                'ra_source':     ra,
                'is_st': False, 'is_csca': True, 'is_cco': False, 'is_appel': False,
                'st_associe':    RegistreST.objects.filter(registre_arrive=ra).first()    if ra else None,
                'cco_associe':   RegistreCCO.objects.filter(registre_arrive=ra).first()   if ra else None,
                'appel_associe': RegistreAppel.objects.filter(registre_arrive=ra).first() if ra else None,
            })

        elif reg_type == 'rrp':
            rp_obj = get_object_or_404(
                RegistreRP.objects.select_related(
                    'registre_arrive', 'registre_arrive__plainte_origine', 'utilisateur_creation'
                ).prefetch_related('personnes_physiques', 'personnes_morales'),
                pk=detail_id
            )
            context.update({
                'reg_detail': rp_obj,
                'is_st': False, 'is_csca': False, 'is_cco': False, 'is_appel': False,
            })
            ra = rp_obj.registre_arrive
            if ra:
                context.update({
                    'ra_source':     ra,
                    'st_associe':    ra.st_details.first(),
                    'csca_associe':  RegistreCSCA.objects.filter(registre_arrive=ra).first(),
                    'cco_associe':   RegistreCCO.objects.filter(registre_arrive=ra).first(),
                    'appel_associe': RegistreAppel.objects.filter(registre_arrive=ra).first(),
                })
                context.update(_resolve_source(ra))
            else:
                context.update({
                    'ra_source': None, 'st_associe': None, 'csca_associe': None,
                    'cco_associe': None, 'appel_associe': None,
                    'plainte_source': None, 'opj_source': None,
                })

        # ── DÉTAIL CCO ← NOUVEAU ─────────────────────────────────────────────
        elif reg_type == 'cco':
            cco_obj = get_object_or_404(
                RegistreCCO.objects.select_related('registre_arrive', 'utilisateur_creation'),
                pk=detail_id
            )
            ra = cco_obj.registre_arrive
            context.update({
                'reg_detail': cco_obj,
                'ra_source':  ra,
                'is_st': False, 'is_csca': False, 'is_cco': True, 'is_appel': False,
            })
            if ra:
                context.update({
                    'st_associe':    ra.st_details.first(),
                    'csca_associe':  RegistreCSCA.objects.filter(registre_arrive=ra).first(),
                    'appel_associe': RegistreAppel.objects.filter(registre_arrive=ra).first(),
                })
                context.update(_resolve_source(ra))

        # ── DÉTAIL APPEL ← NOUVEAU ───────────────────────────────────────────
        elif reg_type == 'appel':
            appel_obj = get_object_or_404(
                RegistreAppel.objects.select_related('registre_arrive', 'utilisateur_creation'),
                pk=detail_id
            )
            ra = appel_obj.registre_arrive
            context.update({
                'reg_detail': appel_obj,
                'ra_source':  ra,
                'is_st': False, 'is_csca': False, 'is_cco': False, 'is_appel': True,
            })
            if ra:
                context.update({
                    'st_associe':   ra.st_details.first(),
                    'csca_associe': RegistreCSCA.objects.filter(registre_arrive=ra).first(),
                    'cco_associe':  RegistreCCO.objects.filter(registre_arrive=ra).first(),
                })
                context.update(_resolve_source(ra))

        else:
            # ── DÉTAIL RA (pre_ra / arrive) ──────────────────────────────────
            ra_obj = get_object_or_404(
                RegistreArrive.objects.select_related('utilisateur_creation'),
                pk=detail_id
            )
            context.update({
                'reg_detail':    ra_obj,
                'ra_source':     ra_obj,
                'is_st': False, 'is_csca': False, 'is_cco': False, 'is_appel': False,
                'st_associe':    ra_obj.st_details.first(),
                'csca_associe':  RegistreCSCA.objects.filter(registre_arrive=ra_obj).first(),
                'cco_associe':   RegistreCCO.objects.filter(registre_arrive=ra_obj).first(),
                'appel_associe': RegistreAppel.objects.filter(registre_arrive=ra_obj).first(),
            })

    # ════════════════════════════════════════════════════════════════════════
    #  5. FORMULAIRE RA (création classique)
    # ════════════════════════════════════════════════════════════════════════
    if mode == 'form' and request.method != 'POST':
        form    = RegistreArriveForm()
        last_id = RegistreArrive.objects.aggregate(Max('id'))['id__max'] or 0
        context['n_enr_provisoire'] = str(last_id + 1).zfill(4)
        context['form'] = form

    elif mode == 'form' and request.method == 'POST':
        form = RegistreArriveForm(request.POST)
        if form.is_valid():
            registre = form.save(commit=False)
            registre.utilisateur_creation = request.user
            registre.save()
            messages.success(request, "Nouveau registre enregistré.")
            return redirect('pac:greffier')
        context['form'] = form

    # ════════════════════════════════════════════════════════════════════════
    #  6. DISPATCH → formulaire ST / RP / CSCA / CCO / APPEL
    # ════════════════════════════════════════════════════════════════════════
    if mode == 'dispatch' and ra_id:
        ra_source = get_object_or_404(RegistreArrive, pk=ra_id)

        if target_type == 'ST':
            context.update({'mode': 'form_st', 'ra_source': ra_source, 'titre': "Transfert en Soit Transmis"})

        elif target_type == 'RP':
            plainte_source, opj_source = _get_sources(ra_source)
            pre_n_be_opj, pre_plaignant, pre_infraction = _get_prefill(ra_source, opj_source, plainte_source)
            context.update({
                'mode':                     'form_rp',
                'ra_source':                ra_source,
                'plainte_source':           plainte_source,
                'opj_source':               opj_source,
                'titre':                    f"Nouveau RP — RA N° {ra_source.n_enr_arrive}",
                'registres_arrive_valides': _ra_valides(request),
                'pre_n_be_opj':             pre_n_be_opj,
                'pre_plaignant':            pre_plaignant,
                'pre_infraction':           pre_infraction,
            })

        elif target_type == 'CSCA':
            context.update({'mode': 'form_csca', 'ra_source': ra_source, 'titre': "Transfert CSCA"})

        # ── CCO ← pré-remplir n_chrono_st et n_dossier depuis ST + RA ──────────
        elif target_type == 'CCO':
            st_lie = ra_source.st_details.first()
            context.update({
                'mode':               'form_cco',
                'ra_source':          ra_source,
                'titre':              f"Nouveau CCO — RA N° {ra_source.n_enr_arrive}",
                # ST → n_chrono_st  |  RA → n_dossier (nbe_dossier ou n_enr_arrive)
                'pre_n_chrono_st':    st_lie.n_chrono  if st_lie else '',
                'pre_n_dossier':      ra_source.nbe_dossier or ra_source.n_enr_arrive or '',
            })

        # ── APPEL ← pré-remplir n_rp et ref_juge depuis RegistreRP lié ──────
        elif target_type == 'RA':   # "RA" dans le <select> = Registre d'Appel
            rp_lie = RegistreRP.objects.filter(registre_arrive=ra_source).first()
            context.update({
                'mode':                   'form_appel',
                'ra_source':              ra_source,
                'titre':                  f"Nouveau Registre d'Appel — RA N° {ra_source.n_enr_arrive}",
                # RP → n_rp (numero_rp)  |  RP → ref_juge_instruction
                'pre_n_rp':               rp_lie.numero_rp           if rp_lie else '',
                'pre_ref_juge':           rp_lie.ref_juge_instruction if rp_lie else '',
            })

        return render(request, 'pac/acc_greffier.html', context)

    # ════════════════════════════════════════════════════════════════════════
    #  7. MODES ÉDITION
    # ════════════════════════════════════════════════════════════════════════
    if mode == 'edit_rp' and detail_id:
        rp_instance = get_object_or_404(
            RegistreRP.objects.select_related('registre_arrive')
                              .prefetch_related('personnes_physiques', 'personnes_morales'),
            pk=detail_id
        )
        plainte_source, opj_source = _get_sources(rp_instance.registre_arrive) if rp_instance.registre_arrive else (None, None)
        context.update({
            'mode':                     'form_rp',
            'rp_instance':              rp_instance,
            'ra_source':                rp_instance.registre_arrive,
            'plainte_source':           plainte_source,
            'opj_source':               opj_source,
            'titre':                    f"Modification — RP N° {rp_instance.numero_rp}",
            'registres_arrive_valides': _ra_valides(request),
        })
        return render(request, 'pac/acc_greffier.html', context)

    if mode == 'edit_st' and detail_id:
        st_instance = get_object_or_404(RegistreST, pk=detail_id)
        context.update({
            'mode': 'form_st', 'st_instance': st_instance,
            'ra_source': st_instance.registre_arrive,
            'titre': "Modification du Soit-Transmis",
        })
        return render(request, 'pac/acc_greffier.html', context)

    if mode == 'edit_csca' and detail_id:
        csca_instance = get_object_or_404(RegistreCSCA, pk=detail_id)
        context.update({
            'mode': 'form_csca', 'csca_instance': csca_instance,
            'ra_source': csca_instance.registre_arrive,
            'titre': f"Modification du dossier CSCA N° {csca_instance.n_chrono}",
        })
        return render(request, 'pac/acc_greffier.html', context)

    # ── EDIT CCO ← NOUVEAU ───────────────────────────────────────────────────
    if mode == 'edit_cco' and detail_id:
        cco_instance = get_object_or_404(RegistreCCO, pk=detail_id)
        context.update({
            'mode': 'form_cco', 'cco_instance': cco_instance,
            'ra_source': cco_instance.registre_arrive,
            'titre': f"Modification CCO N° {cco_instance.n_chrono}",
        })
        return render(request, 'pac/acc_greffier.html', context)

    # ── EDIT APPEL ← NOUVEAU ─────────────────────────────────────────────────
    if mode == 'edit_appel' and detail_id:
        appel_instance = get_object_or_404(RegistreAppel, pk=detail_id)
        context.update({
            'mode': 'form_appel', 'appel_instance': appel_instance,
            'ra_source': appel_instance.registre_arrive,
            'titre': f"Modification Appel N° {appel_instance.n_chrono_appel}",
        })
        return render(request, 'pac/acc_greffier.html', context)

    # ════════════════════════════════════════════════════════════════════════
    #  8. FILTRAGE / RECHERCHE / PAGINATION
    # ════════════════════════════════════════════════════════════════════════
    if reg_type == "st":
        queryset = RegistreST.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('registre_arrive', 'utilisateur_creation').order_by('-date_st')
        context['titre'] = "Registre du Soit Transmis (ST)"

    elif reg_type == 'csca':
        queryset = RegistreCSCA.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('registre_arrive', 'utilisateur_creation').order_by('-date_csca')
        context['titre'] = "Registre CSCA"

    elif reg_type == 'rrp':
        queryset = RegistreRP.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('registre_arrive', 'utilisateur_creation').order_by('-date_creation')
        context['titre'] = "Registre RP"

    elif reg_type == 'cco':   # ← NOUVEAU
        queryset = RegistreCCO.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('registre_arrive', 'utilisateur_creation').order_by('-date_creation')
        context['titre'] = "Registre CCO"

    elif reg_type == 'appel':   # ← NOUVEAU
        queryset = RegistreAppel.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('registre_arrive', 'utilisateur_creation').order_by('-date_creation')
        context['titre'] = "Registre d'Appel"

    else:
        queryset = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('utilisateur_creation').prefetch_related('st_details')
        if reg_type == "arrive":
            queryset = queryset.filter(n_enr_arrive__isnull=False).order_by('-date_arrivee')
            context['titre'] = "Registre Arrivée"
        else:
            queryset = queryset.filter(n_enr_arrive__isnull=True).order_by('-date_arrivee')
            context['titre'] = "Pre-RA"

    # Recherche (elif pour ne pas écraser le queryset)
    if search_query:
        if reg_type == "st":
            queryset = queryset.filter(
                Q(objet__icontains=search_query) |
                Q(destinataire__icontains=search_query) |
                Q(registre_arrive__n_enr_arrive__icontains=search_query)
            )
        elif reg_type == "csca":
            queryset = queryset.filter(
                Q(objet__icontains=search_query) |
                Q(demandeur__icontains=search_query) |
                Q(registre_arrive__n_enr_arrive__icontains=search_query)
            )
        elif reg_type == 'rrp':
            queryset = queryset.filter(
                Q(numero_rp__icontains=search_query) |
                Q(plaignant__icontains=search_query) |
                Q(infraction__icontains=search_query)
            )
        elif reg_type == 'cco':
            queryset = queryset.filter(
                Q(n_chrono__icontains=search_query) |
                Q(n_dossier__icontains=search_query) |
                Q(n_chrono_st__icontains=search_query) |
                Q(registre_arrive__n_enr_arrive__icontains=search_query)
            )
        elif reg_type == 'appel':
            queryset = queryset.filter(
                Q(n_chrono_appel__icontains=search_query) |
                Q(n_rp__icontains=search_query) |
                Q(inculpation__icontains=search_query)
            )
        else:
            queryset = queryset.filter(
                Q(n_enr_arrive__icontains=search_query) |
                Q(expediteur__icontains=search_query) |
                Q(observation__icontains=search_query)
            )

    paginator = Paginator(queryset, 10)
    page_obj  = paginator.get_page(page_number)
    context['registres'] = page_obj
    context['page_obj']  = page_obj

    return render(request, 'pac/acc_greffier.html', context)


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS PRIVÉS (à placer juste après acc_greffier dans views.py)
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_source(ra):
    """Retourne dict {plainte_source, opj_source} depuis un RegistreArrive."""
    if ra.nature == 'opj' and ra.n_chrono_opj:
        return {
            'opj_source':     OPJ.objects.filter(n_chrono_opj=ra.n_chrono_opj).select_related('utilisateur_creation').first(),
            'plainte_source': None,
        }
    elif ra.plainte_origine:
        return {'plainte_source': ra.plainte_origine, 'opj_source': None}
    elif ra.nbe_dossier:
        return {
            'plainte_source': Plainte.objects.filter(n_chrono_tkk=ra.nbe_dossier).first(),
            'opj_source': None,
        }
    return {'plainte_source': None, 'opj_source': None}


def _get_sources(ra):
    """Retourne (plainte_source, opj_source) depuis un RegistreArrive."""
    if not ra:
        return None, None
    if ra.nature == 'opj' and ra.n_chrono_opj:
        return None, OPJ.objects.filter(n_chrono_opj=ra.n_chrono_opj).first()
    elif ra.plainte_origine:
        return ra.plainte_origine, None
    elif ra.nbe_dossier:
        return Plainte.objects.filter(n_chrono_tkk=ra.nbe_dossier).first(), None
    return None, None


def _get_prefill(ra_source, opj_source, plainte_source):
    """Retourne (pre_n_be_opj, pre_plaignant, pre_infraction) pour pré-remplir RP."""
    if opj_source:
        return opj_source.n_chrono_opj or '', opj_source.ny_mpitory or '', opj_source.tranga_kolikoly or ''
    elif plainte_source:
        return '', plainte_source.ny_mpitory or '', plainte_source.tranga_kolikoly or ''
    return '', ra_source.expediteur or '', ra_source.objet_demande or ''


def _ra_valides(request):
    """QuerySet des RA validés (avec n_enr_arrive) du même PAC."""
    return RegistreArrive.objects.filter(
        utilisateur_creation__localite=request.user.localite,
        n_enr_arrive__isnull=False
    ).order_by('-date_arrivee')

