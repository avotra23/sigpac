from asyncio.windows_events import NULL
from django.db import models
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
        default=timezone.now,
        editable=False, 
        verbose_name="Dates"
    )

    # Champs du formulaire
    ny_mpitory = models.TextField(verbose_name="Ny Mpitory (Le Plaignant)")
    tranga_kolikoly = models.TextField(verbose_name="Tranga Kolikoly (Le Fait/Acte de Corruption)")
    ilay_olona_kolikoly = models.TextField(verbose_name="Ilay Olona Manao kolikoly (L'auteur de la corruption)")
    toorna_birao = models.TextField(verbose_name="Toerana - Birao - Sampan-draharaha manao ilay kolikoly (Lieu - Bureau - Service de la corruption)", blank=True, null=True)

    
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
            
            # 3. Seconde sauvegarde (MISE À JOUR) pour enregistrer n_chrono_tkk ET utilisateur_creation
            # Nous assumons que l'utilisateur_creation est défini avant le premier super().save() dans la vue/form.
            # Si l'utilisateur est passé via kwargs, récupérez-le ici :
            # user = kwargs.pop('user', None)
            # if user and not self.utilisateur_creation: self.utilisateur_creation = user
            
            super().save(update_fields=['n_chrono_tkk', 'utilisateur_creation']) 
            return
            
        # Sauvegarde normale (Mise à jour d'une instance existante)
        super().save(*args, **kwargs)

# Nécessite les STATUT_CHOICES définis ci-dessus

class RegistreArrive(models.Model):
    NATURE_CHOICES = [
        ('lettre', 'Lettre'),
        ('email', 'Email'),
        ('fax', 'Fax'),
        ('main', 'Dépôt à la main'),
        ('plainte', 'Plainte en ligne'),
        ('opj', 'OPJ'),
    ]
    
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
    provenance = models.TextField(verbose_name="Provenance")
    texte_correspondance = models.TextField(verbose_name="Texte de la correspondance")
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
    n_plainte_associe = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name="N° Plainte Associée"
    )
    # --- Fin des Champs de Traçabilité ---

    class Meta:
        verbose_name = "Registre Arrivé"
        verbose_name_plural = "Registres Arrivés"
        ordering = ['-date_arrivee', '-id']

    def __str__(self):
        return f"ENR N° {self.n_enr_arrive}"
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


    def attribuer_ra(self, prefixe="RA"):
        if self.n_enr_arrive is None or self.n_enr_arrive == '':
            new_id = self.id
            self.n_enr_arrive = f"{prefixe}/{str(new_id).zfill(4)}" 
            self.est_valide = True
            self.save(update_fields=['n_enr_arrive', 'est_valide'])
            return self.n_enr_arrive
        return self.n_enr_arrive