from asyncio.windows_events import NULL
from django.db import models, transaction
from django.db.models import  Max
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone 
import os
# Create your models here.

class Direction(models.Model):
    nom_dir = models.CharField(max_length=150)
    def __str__(self):
        return self.nom_dir

class Fonction(models.Model):
    nom_fc = models.CharField(max_length=150)
    direction = models.ForeignKey(Direction,on_delete=models.CASCADE)
    def __str__(self):
        return self.nom_fc

class Poste(models.Model):
    id_dir = models.ForeignKey(Direction,on_delete=models.CASCADE)
    id_fonc = models.ForeignKey(Fonction, on_delete=models.CASCADE)
    def __str__(self):
        return f"{self.id_fonc.nom_fc} ({self.id_dir.nom_dir})"

#Gestion utilisateur personnalise
class UtilisateurManager(BaseUserManager):
    def create_user(self, email,password=None, **extra_fields):
        if not email:
            raise ValueError("Les utilisateurs doivent avoirs une email")
        email = self.normalize_email(email)
        user = self.model(email = email, **extra_fields)   
        user.set_password(password)
        user.save(using=self._db)
        return user 
    def create_superuser(self, email, password=None, **extra_fields):
        # Les superutilisateurs doivent avoir les permissions d'administration
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)
    
    def get_by_natural_key(self, email_):
        """
        Permet à Django de récupérer un utilisateur en utilisant son 'natural key' (email)
        """
        return self.get(email=email_)
    
class Localite(models.Model):
    nom_loc = models.CharField(max_length=100)
    def __str__(self):
        return self.nom_loc

#Utilisateur personnalise
class Utilisateur(AbstractBaseUser):
    #Les champs obligatoires
    email = models.EmailField(verbose_name='Adresse e-mail',max_length=200,unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    #Champs personnel 
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=200)
    telephone = models.IntegerField(null=True)
    poste  = models.ForeignKey(Poste,on_delete=models.SET_NULL,null=True)
    localite = models.ForeignKey(Localite,on_delete=models.SET_NULL,null = True)
    photo = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    matricule = models.CharField(
    max_length=20, 
    null=True,             # Garde null=True temporairement pour la migration
    blank=False,           # Rend le champ obligatoire dans les formulaires Django
    verbose_name="Matricule",
    help_text="Format : MAT-000 (Max 10 Mo pour les pièces jointes associées)" # Optionnel
)
    
    #Configuration du connexion
    USERNAME_FIELD = 'email'

    #Champs apparus dans la creation superuser
    REQUIERD_FIELD = ['nom','prenom','telephone']
    objects = UtilisateurManager()

    groups = models.ManyToManyField('auth.Group',blank=True,related_name="utilisateur_groups",related_query_name="utilisateur")
    user_permissions = models.ManyToManyField('auth.Permission',blank=True,related_name="utilisateur_permissions",related_query_name="utilisateur")
    def __str__(self):
        return self.email

    #Obligatoire pour determiner les permissions
    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        return False
    
    def has_module_perms(self, app_label):
        return self.is_staff

    last_password_change = models.DateTimeField(null=True, blank=True)
    
    # Ajoutez une méthode pour vérifier si le changement est autorisé
    def peut_changer_mdp(self):
        if not self.last_password_change:
            return True
        # Vérifie si 90 jours (3 mois) se sont écoulés
        delai = timezone.now() - self.last_password_change
        return delai.days >= 90
    
STATUT_CHOICES = [
        ('ATTENTE', 'En attente'),
        ('COURS', 'En cours de traitement'),
        ('TRAITEE', 'Traitée'),
        ('DISPATCHE', 'Dispatche'),
        ('CSS', 'Classer sans suite'),
    ]



def plainte_directory_path(instance, filename):
    return f'plaintes/{instance.pk}/{filename}'


class Plainte(models.Model):
    # Champs auto-générés et non modifiables
    n_chrono_tkk = models.CharField(
        max_length=50,  
        editable=False, 
        verbose_name="N° Chrono TKK"
    )
    date_plainte = models.DateField(
    auto_now_add=True, # Définit la date automatiquement à la création
    verbose_name="Dates")

    # Champs du formulaire
    ny_mpitory = models.TextField(verbose_name="Ny Mpitory (Le Plaignant)")
    tranga_kolikoly = models.TextField(verbose_name="Tranga Kolikoly (Le Fait/Acte de Corruption)")
    ilay_olona_kolikoly = models.TextField(verbose_name="Ilay Olona Manao kolikoly (L'auteur de la corruption)")
    toorna_birao = models.TextField(verbose_name="Toerana - Birao - Sampan-draharaha manao ilay kolikoly (Lieu - Bureau - Service de la corruption)", blank=True, null=True)

    observation = models.TextField(verbose_name="Antony", blank=True, null=True)
    
    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='ATTENTE',
        verbose_name="Statut de la plainte"
    )

    def __str__(self):
        return f"Plainte N° {self.n_chrono_tkk}"
        
    
    utilisateur_creation = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, # Si l'utilisateur est supprimé, le champ est mis à NULL
        null=True, 
        editable=False, 
        related_name='plaintes_creees', 
        verbose_name="Créé par"
    )
    est_anonyme = models.BooleanField(
        default=False, 
        verbose_name="Plainte Anonyme"
    )
    utilisateur_modification = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, # Optionnel : peut être vide si jamais modifié
        related_name='plaintes_modifiees', 
        verbose_name="Dernière modification par"
    )
    LOCALITE_CHOICES = [
        ('ANTANANARIVO', 'ANTANANARIVO'),
        ('FIANARANTSOA', 'FIANARANTSOA'),
        ('MAHAJANGA', 'MAHAJANGA'),
    ]
    pac_affecte = models.CharField(
        max_length=50, 
        choices=LOCALITE_CHOICES,
        null=True,  # Peut être NULL tant que le DCN n'a pas dispatché
        blank=True,
        verbose_name="PAC Affecté"
    )
    # --- Fin des Champs de Traçabilité ---

    piece_jointe = models.FileField(
        upload_to=plainte_directory_path,
        blank=True,
        null=True,
        verbose_name="Pièce jointe (PDF, Image...)",
        max_length=255
    )

    class Meta:
        verbose_name = "Plainte en ligne"
        verbose_name_plural = "Plaintes en ligne"
        ordering = ['-date_plainte']

    # ... (Votre méthode __str__)
    def delete(self, *args, **kwargs):
        """
        Surcharge de la méthode delete() pour supprimer le fichier physique
        lié à la pièce jointe avant de supprimer l'instance de la BD.
        """
        # 1. Suppression du fichier physique, si il existe
        if self.piece_jointe:
            # Vérifie si le fichier existe sur le disque avant de tenter de le supprimer
            if os.path.isfile(self.piece_jointe.path):
                self.piece_jointe.delete(save=False) # Supprime le fichier du système de fichiers
        
        # 2. Appel de la méthode delete() du parent pour supprimer l'entrée de la base de données
        super().delete(*args, **kwargs)
    # La logique de save() DOIT ÊTRE MODIFIÉE pour gérer l'utilisateur_creation
    def save(self, *args, **kwargs):
        is_new = not self.pk 

        # Si c'est une nouvelle plainte, nous devons la sauvegarder pour obtenir l'ID
        if is_new:
            # 1. Sauvegarde initiale pour obtenir l'ID (pk)
            super().save(*args, **kwargs) 
            
            # 2. Génération du numéro de chrono basé sur l'ID
            year = timezone.now().year
            sequential_part = str(self.id).zfill(8) 
            self.n_chrono_tkk = f"DPL: {sequential_part}/{year}"
            
            super().save(update_fields=['n_chrono_tkk', 'utilisateur_creation']) 
            return
            
        # Sauvegarde normale (Mise à jour d'une instance existante)
        super().save(*args, **kwargs)
    
    @property
    def pieces_jointes_url(self):
        if self.piece_jointe:
            return self.piece_jointe.url
        return None

class OPJ(models.Model):
    # Champs auto-générés et non modifiables
    n_chrono_opj = models.CharField(
        max_length=50,  
        editable=False, 
        verbose_name="N° Chrono TKK"
    )
    date_plainte = models.DateField(
    auto_now_add=True, # Définit la date automatiquement à la création
    verbose_name="Dates")

    # Champs du formulaire
    ny_mpitory = models.TextField(verbose_name="Ny Mpitory (Le Plaignant)")
    tranga_kolikoly = models.TextField(verbose_name="Tranga Kolikoly (Le Fait/Acte de Corruption)")
    ilay_olona_kolikoly = models.TextField(verbose_name="Ilay Olona Manao kolikoly (L'auteur de la corruption)")
    toerana_birao = models.TextField(verbose_name="Toerana - Birao - Sampan-draharaha manao ilay kolikoly (Lieu - Bureau - Service de la corruption)", blank=True, null=True)

    observation = models.TextField(verbose_name="Antony", blank=True, null=True)
    
    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='ATTENTE',
        verbose_name="Statut de la plainte"
    )

    def __str__(self):
        return f"Plainte N° {self.n_chrono_opj}"
        
    
    utilisateur_creation = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        editable=False, 
        related_name='opj_crees',  # Changé ici
        verbose_name="Créé par"
    )

    utilisateur_modification = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        related_name='opj_modifies', # Changé ici
        verbose_name="Dernière modification par"
    )
    LOCALITE_CHOICES = [
        ('ANTANANARIVO', 'ANTANANARIVO'),
        ('FIANARANTSOA', 'FIANARANTSOA'),
        ('MAHAJANGA', 'MAHAJANGA'),
    ]
    pac_affecte = models.CharField(
        max_length=50, 
        choices=LOCALITE_CHOICES,
        null=True,  # Peut être NULL tant que le DCN n'a pas dispatché
        blank=True,
        verbose_name="PAC Affecté"
    )
    # --- Fin des Champs de Traçabilité ---

    piece_jointe = models.FileField(
        upload_to=plainte_directory_path,
        blank=True,
        null=True,
        verbose_name="Pièce jointe (PDF, Image...)",
        max_length=255
    )

    class Meta:
        verbose_name = "Plaintes OPJ"
        verbose_name_plural = "Plaintes OPJ"
        ordering = ['-date_plainte']

    # ... (Votre méthode __str__)
    def delete(self, *args, **kwargs):
        """
        Surcharge de la méthode delete() pour supprimer le fichier physique
        lié à la pièce jointe avant de supprimer l'instance de la BD.
        """
        # 1. Suppression du fichier physique, si il existe
        if self.piece_jointe:
            # Vérifie si le fichier existe sur le disque avant de tenter de le supprimer
            if os.path.isfile(self.piece_jointe.path):
                self.piece_jointe.delete(save=False) # Supprime le fichier du système de fichiers
        
        # 2. Appel de la méthode delete() du parent pour supprimer l'entrée de la base de données
        super().delete(*args, **kwargs)
    # La logique de save() DOIT ÊTRE MODIFIÉE pour gérer l'utilisateur_creation
    def save(self, *args, **kwargs):
        is_new = not self.pk 

        # Si c'est une nouvelle plainte, nous devons la sauvegarder pour obtenir l'ID
        if is_new:
            # 1. Sauvegarde initiale pour obtenir l'ID (pk)
            super().save(*args, **kwargs) 
            
            # 2. Génération du numéro de chrono basé sur l'ID
            year = timezone.now().year
            sequential_part = str(self.id).zfill(8) 
            self.n_chrono_opj = f"DPSA: {sequential_part}/{year}"
            
            super().save(update_fields=['n_chrono_opj', 'utilisateur_creation']) 
            return
            
        # Sauvegarde normale (Mise à jour d'une instance existante)
        super().save(*args, **kwargs)
    
    @property
    def pieces_jointes_url(self):
        if self.piece_jointe:
            return self.piece_jointe.url
        return None
    
#Pour discussion entre user
class MessageChat(models.Model):
    # Contextes (Source 1, 4)
    plainte = models.ForeignKey(Plainte, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    opj = models.ForeignKey(OPJ, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    
    # Acteurs (Source 3)
    expediteur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='envoyes')
    destinataire = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='recus')
    
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ['date_envoi']


class RegistreArrive(models.Model):
    NATURE_CHOICES = [
        ('lettre', 'Lettre'),
        ('email', 'Email'),
        ('fax', 'Fax'),
        ('main', 'Dépôt à la main'),
        ('plainte', 'Plainte en ligne'),
        ('opj', 'OPJ'),
    ]
    #Champs suivie du plainte 
    plainte_origine = models.ForeignKey(
        Plainte, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="registres_entree",
        verbose_name="Plainte TKK liée"
    )

    # Ce champ contiendra la valeur textuelle du n_chrono_tkk pour affichage/recherche facile
    # nbe : numero plainte en ligne associer
    nbe_dossier = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name="N° Dossier (TKK)"
    )

    # nnumero plainte OPJ associer si venant de OPJ
    n_chrono_opj = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name="N° Chrono OPJ"
    )
   
    # Champs auto-générés et non modifiables
    n_enr_arrive = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False, 
        null=True,           
        blank=True,
        verbose_name="N° ENR Arrivé"
    )
    est_valide = models.BooleanField(
        default=False,
        verbose_name="Validé (avec N° RA)"
    )
    date_arrivee = models.DateField(
        default=timezone.now,
        verbose_name="Date d’arrivée"
    )

    # Champs du formulaire
    date_correspondance = models.DateField(verbose_name="Date Correspondance")
    nature = models.CharField(max_length=50, choices=NATURE_CHOICES, verbose_name="Nature")
    expediteur = models.TextField(verbose_name="Expediteur",default="Non spécifié")
    objet_demande = models.TextField(verbose_name="Objet de la demande",default="Non spécifié")
    observation = models.TextField(verbose_name="Observation", blank=True, null=True)
    
    # Champ Statut standardisé
    statut_traitement = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES, # Utilisation des mêmes CHOICES
        default='COURS', 
        verbose_name="Statut du Traitement"
    )

    utilisateur_creation = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        editable=False, 
        related_name='registres_crees', 
        verbose_name="Créé par"
    )
    utilisateur_modification = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='registres_modifies', 
        verbose_name="Dernière modification par"
    )
    
    # --- Fin des Champs de Traçabilité ---

    class Meta:
        verbose_name = "Registre Arrivé"
        verbose_name_plural = "Registres Arrivés"
        ordering = ['-date_arrivee', '-id']

    def __str__(self):
        return f"ENR N° {self.n_enr_arrive}"
        
    def save(self, *args, **kwargs):
        if self.plainte_origine:
            self.nbe_dossier = self.plainte_origine.n_chrono_tkk
            # Optionnel : Forcer la nature à 'plainte' si elle est liée
            self.nature = 'plainte'
        super().save(*args, **kwargs)


    def attribuer_ra(self, prefixe="RA"):
        if self.n_enr_arrive is None or self.n_enr_arrive == '':
            new_id = self.id
            self.n_enr_arrive = f"{prefixe}/{str(new_id).zfill(4)}" 
            self.est_valide = True
            self.save(update_fields=['n_enr_arrive', 'est_valide'])
            return self.n_enr_arrive
        return self.n_enr_arrive


class RegistreST(models.Model):
    # Lien unique avec le Registre Arrivé
    registre_arrive = models.ForeignKey(
        RegistreArrive, 
        on_delete=models.CASCADE, 
        related_name='st_details', # Pluriel car il peut y en avoir plusieurs
        verbose_name="N° RA lié"
    )
    
    # Champs du formulaire
    n_chrono = models.CharField(max_length=100, unique=True, editable=False, null=True, blank=True)
    date_st = models.DateField(default=timezone.now, verbose_name="Date")
    objet = models.TextField(verbose_name="Objet")
    destinataire = models.TextField(verbose_name="Destinataire")
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    rappel = models.TextField(blank=True, null=True, verbose_name="Rappel")
    resultat = models.TextField(blank=True, null=True, verbose_name="Résultat")

    # Traçabilité
    utilisateur_creation = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, editable=False, related_name='st_crees')
    utilisateur_modification = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name='st_modifies')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.n_chrono:
            with transaction.atomic():
                current_year = timezone.now().year
                # Récupère le dernier ID global pour garantir l'unicité
                last_id = RegistreST.objects.aggregate(models.Max('id'))['id__max'] or 0
                next_number = last_id + 1
                self.n_chrono = f"ST/{current_year}/{str(next_number).zfill(4)}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Registre ST"
        ordering = ['-date_creation']

class RegistreCSCA(models.Model):
    # Relation avec le Registre Arrivé
    registre_arrive = models.OneToOneField(
        'RegistreArrive', 
        on_delete=models.CASCADE, 
        related_name='csca_detail',
        verbose_name="N° RA lié"
    )
    
    # n_chrono est en editable=False pour ne pas apparaître dans les formulaires auto-générés
    n_chrono = models.CharField(max_length=100, unique=True, editable=False, null=True, blank=True)
    date_csca = models.DateField(default=timezone.now, verbose_name="Date")
    demandeur = models.CharField(max_length=255, verbose_name="Demandeur")
    entite = models.CharField(max_length=255, verbose_name="Entité")
    objet = models.TextField(verbose_name="Objet")
    requisitoire_mp = models.TextField(verbose_name="Réquisitoire du MP")
    intitule = models.TextField(verbose_name="Intitulé")
    transmission_president = models.TextField(verbose_name="Transmission Président", blank=True, null=True)
    decision = models.TextField(verbose_name="Décision")
    appel = models.TextField(verbose_name="Appel", blank=True, null=True)
    resultat_appel = models.TextField(verbose_name="Résultat appel", blank=True, null=True)

    # Traçabilité
    utilisateur_creation = models.ForeignKey('Utilisateur', on_delete=models.SET_NULL, null=True, editable=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.n_chrono:
            with transaction.atomic():
                current_year = timezone.now().year
                # On cherche le dernier ID pour générer le numéro suivant
                last_entry = RegistreCSCA.objects.select_for_update().order_by('-id').first()
                last_id = last_entry.id if last_entry else 0
                next_number = last_id + 1
                
                # Formatage du chrono : CSCA / ANNEE / NUMERO sur 4 chiffres
                self.n_chrono = f"CSCA/{current_year}/{str(next_number).zfill(4)}"
        
        super(RegistreCSCA, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Registre CSCA"
        ordering = ['-date_creation']