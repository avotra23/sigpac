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
    # --- RÉCUPÉRATION DES PARAMÈTRES ---
    mode = request.GET.get('mode', 'list')
    reg_type = request.GET.get('type', 'pre_ra')  # Par défaut : Pre-RA
    detail_id = request.GET.get('detail_id')
    validation_id = request.GET.get('valider_id')
    ra_id = request.GET.get('ra_id')
    target_type = request.GET.get('target_type')
    
    # Paramètres de recherche et pagination
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)

    context = {
        'user': request.user,
        'groups': "greffier",
        'mode': mode,
        'reg_type': reg_type,
        'search_query': search_query,
        'date_arrivee_systeme': timezone.now().strftime("%Y-%m-%d"),
    }
    # Enregistrement en ST
    if request.method == 'POST' and mode == 'save_st':
        try:
            with transaction.atomic():
                st_id = request.POST.get('st_id')
                ra_id_post = request.POST.get('ra_id')
                ra_source = get_object_or_404(RegistreArrive, pk=ra_id_post)

                # Si st_id existe, on modifie, sinon on crée
                if st_id:
                    st_obj = get_object_or_404(RegistreST, pk=st_id)
                    message = "Dossier ST mis à jour"
                else:
                    st_obj = RegistreST(registre_arrive=ra_source, utilisateur_creation=request.user)
                    message = "Dossier enregistré au ST avec succès"

                st_obj.date_st = request.POST.get('date_st')
                st_obj.objet = request.POST.get('objet')
                st_obj.destinataire = request.POST.get('destinataire')
                st_obj.observation = request.POST.get('observation')
                st_obj.rappel = request.POST.get('rappel')
                st_obj.resultat = request.POST.get('resultat')
                st_obj.save()

                return JsonResponse({'status': 'success', 'message': message})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    # Enregistrement en CSCA
    if request.method == 'POST' and mode == 'save_csca':
        try:
            with transaction.atomic():
                ra_id_post = request.POST.get('ra_id')
                ra_source = get_object_or_404(RegistreArrive, pk=ra_id_post)
                
                # On utilise les noms exacts de votre modèle RegistreCSCA
                csca_obj = RegistreCSCA.objects.create(
                    registre_arrive=ra_source,
                    utilisateur_creation=request.user,
                    date_csca=request.POST.get('date_csca'),
                    demandeur=request.POST.get('demandeur'),
                    entite=request.POST.get('entite'),
                    objet=request.POST.get('objet'),
                    intitule=request.POST.get('intitule'),
                    requisitoire_mp=request.POST.get('requisitoire_mp'),
                    decision=request.POST.get('decision'),
                    transmission_president=request.POST.get('transmission_president'),
                    appel=request.POST.get('appel'),
                    resultat_appel=request.POST.get('resultat_appel')
                )
                return JsonResponse({'status': 'success', 'message': f"Enregistré sous le N° {csca_obj.n_chrono}"})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    # --- 2. LOGIQUE VALIDATION (ATTRIBUTION N° RA) ---
    if validation_id:
        registre = get_object_or_404(RegistreArrive, pk=validation_id, utilisateur_creation__localite=request.user.localite)
        n_ra = registre.attribuer_ra()
        messages.success(request, f"Validé avec le N° : {n_ra}")
        return redirect('pac:greffier')
    # --- 3. LOGIQUE DÉTAILS ---
    if detail_id:
        if reg_type == 'st':
            context['reg_detail'] = get_object_or_404(
                RegistreST.objects.select_related('registre_arrive', 'utilisateur_creation'), 
                pk=detail_id
            )
            context['is_st'] = True
        elif reg_type == 'csca':
            context['titre'] = "Registre CSCA"
        else:
            # On récupère le RA
            ra_obj = get_object_or_404(
                RegistreArrive.objects.select_related('utilisateur_creation'), 
                pk=detail_id
            )
            context['reg_detail'] = ra_obj
            # ON RÉCUPÈRE LE DERNIER ST LIÉ (C'est ici que ça se joue)
            context['st_associe'] = ra_obj.st_details.first() 
            context['is_st'] = False
            
        context['mode'] = 'detail'
        context['reg_type'] = reg_type
        
       # --- 4. LOGIQUE FORMULAIRE RA (CRÉATION) ---
    if mode == 'form' or (request.method == 'POST' and mode != 'save_st' and mode != 'dispatch'):
        if request.method == 'POST':
            form = RegistreArriveForm(request.POST)
            if form.is_valid():
                registre = form.save(commit=False)
                registre.utilisateur_creation = request.user
                registre.save()
                messages.success(request, "Nouveau registre enregistré.")
                return redirect('pac:greffier')
        else:
            form = RegistreArriveForm()
            last_id = RegistreArrive.objects.aggregate(Max('id'))['id__max'] or 0
            context['n_enr_provisoire'] = str(last_id + 1).zfill(4)
        context['form'] = form

    # --- 5. LOGIQUE DE REDIRECTION VERS FORMULAIRE ST (SWITCH) ---
    if mode == 'dispatch' and ra_id:
        ra_source = get_object_or_404(RegistreArrive, pk=ra_id)
        if target_type == 'ST':
            context.update({
                'mode': 'form_st',
                'ra_source': ra_source,
                'titre': "Transfert en Soit Transmis",  
            })
        elif target_type == 'CSCA':
            context.update({'mode': 'form_csca', 
                            'ra_source': ra_source, 
                            'titre': "Transfert CSCA"})
        return render(request, 'pac/acc_greffier.html', context)

    # --- 6. FILTRAGE, RECHERCHE ET PAGINATION ---
    # Sélection du Queryset de base selon le type
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
    else:
        # Base pour Arrivée et Pre-RA
        queryset = RegistreArrive.objects.filter(
            utilisateur_creation__localite=request.user.localite
        ).select_related('utilisateur_creation').prefetch_related('st_details')

        if reg_type == "arrive":
            queryset = queryset.filter(n_enr_arrive__isnull=False).order_by('-date_arrivee')
            context['titre'] = "Registre Arrivée"
        else:
            queryset = queryset.filter(n_enr_arrive__isnull=True).order_by('-date_arrivee')
            context['titre'] = "Pre-RA"

    # Application de la recherche (Search)
    if search_query:
        if reg_type == "st":
            queryset = queryset.filter(
                Q(objet__icontains=search_query) | 
                Q(destinataire__icontains=search_query) |
                Q(registre_arrive__n_enr_arrive__icontains=search_query)
            )
        else:
            queryset = queryset.filter(
                Q(n_enr_arrive__icontains=search_query) | 
                Q(expediteur__icontains=search_query) | 
                Q(observation__icontains=search_query)
            )

    # Pagination (10 éléments par page)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(page_number)
    
    context['registres'] = page_obj
    context['page_obj'] = page_obj

    #---7 Gestion des modification ST
    if mode == 'edit_st' and detail_id:
        st_instance = get_object_or_404(RegistreST, pk=detail_id)
        context.update({
            'mode': 'form_st',
            'st_instance': st_instance,
            'ra_source': st_instance.registre_arrive, # On récupère le RA lié
            'titre': "Modification du Soit-Transmis",
        })
        return render(request, 'pac/acc_greffier.html', context)
    return render(request, 'pac/acc_greffier.html', context)




