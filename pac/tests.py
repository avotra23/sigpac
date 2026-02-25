from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import Group
from utilisateur.models import Localite, Plainte
from rest_framework import status
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class PacViewsTestCase(TestCase):
    def setUp(self):
        # 1. Création des Groupes (Assurez-vous que les noms correspondent à vos vues)
        self.group_public = Group.objects.create(name='public')
        self.group_dcn = Group.objects.create(name='DCN')

        # 2. Création des Utilisateurs (Utilisation de l'email)
        self.user_public = User.objects.create_user(
            email='citoyen@test.com', 
            password='password123'
        )
        self.user_public.groups.add(self.group_public)
        
        self.user_dcn = User.objects.create_user(
            email='dcn@test.com', 
            password='password123'
        )
        self.user_dcn.groups.add(self.group_dcn)
        
        # 3. Données de base
        self.loc = Localite.objects.create(nom_loc="ANTANANARIVO")

        # 4. Création d'une plainte de test
        self.plainte = Plainte.objects.create(
            tranga_kolikoly="Corruption test",
            utilisateur_creation=self.user_public,
            pac_affecte="ANTANANARIVO",
            statut="ATTENTE"
        )

    def test_accueil_redirect_public(self):
        """Vérifie que l'utilisateur public est redirigé vers sa page après accueil"""
        self.client.login(email='citoyen@test.com', password='password123')
        response = self.client.get(reverse('pac:accueil'))
        self.assertRedirects(response, reverse('pac:public'))

    def test_accueil_non_connecte(self):
        """Vérifie la redirection vers le login si non connecté"""
        response = self.client.get(reverse('pac:accueil'))
        self.assertEqual(response.status_code, 302)
        # On vérifie que 'login' est présent dans l'URL de redirection
        self.assertIn('login', response.url)

    def test_api_public_list(self):
        """Vérifie que l'utilisateur voit ses propres plaintes via l'API"""
        self.client.login(email='citoyen@test.com', password='password123')
        response = self.client.get(reverse('pac:api_public_plaintes'), {'mode': 'list'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # On vérifie le contenu de la plainte au lieu du numéro chrono (qui change)
        self.assertEqual(response.data['plaintes'][0]['tranga_kolikoly'], "Corruption test")

    def test_api_public_delete(self):
        """Vérifie la suppression d'une plainte via l'API"""
        self.client.login(email='citoyen@test.com', password='password123')
        url = reverse('pac:api_public_delete', kwargs={'plainte_id': self.plainte.pk})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Plainte.objects.filter(pk=self.plainte.pk).exists())

    def test_plainte_anonyme_api(self):
        """Vérifie la création d'une plainte anonyme (Erreur 400 possible si champs manquants)"""
        data = {
            "ny_mpitory": "Anonyme", # Ajoute ce champ obligatoire
            "tranga_kolikoly": "Corruption anonyme",
            "ilay_olona_kolikoly": "Individu X",
            "andray_fepetra": "Avertissement",
            "pac_affecte": "ANTANANARIVO"
        }
        response = self.client.post(reverse('pac:api_plainte_anonyme'), data)
        
        # Débogage si erreur 400
        if response.status_code == 400:
            print(f"\nErreurs validation Plainte Anonyme: {response.data}")
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('qr_code_base64', response.data)

    def test_dcn_dispatch_plainte(self):
        """Vérifie le dispatch par un DCN (Erreur 403 possible si problème de groupe)"""
        self.client.login(email='dcn@test.com', password='password123')
        
        data = {
            'mode': 'dispatch',
            'idplainte': self.plainte.id,
            'pac': 'MAHAJANGA'
        }
        response = self.client.post(reverse('pac:api_dcn_plaintes'), data)
        
        # Débogage si erreur 403
        if response.status_code == 403:
            print("\nAccès refusé pour le DCN. Vérifiez le nom du groupe dans la vue (DCN vs dcn).")
            
        self.assertEqual(response.status_code, 200)
        self.plainte.refresh_from_db()
        self.assertEqual(self.plainte.statut, "DISPATCHE")
        self.assertEqual(self.plainte.pac_affecte, "MAHAJANGA")