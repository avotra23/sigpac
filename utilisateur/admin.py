from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
# Register your models here.


admin.site.register(Localite)
admin.site.register(Poste)
admin.site.register(Direction)
admin.site.register(Fonction)

#Modification affichage admin
class affiche(admin.ModelAdmin): 
    
    # A afficher en colonne
    list_display = ('email', 'nom', 'prenom', 'is_active', 'is_staff', 'poste','localite')
    
    # Filtre
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    
    # Mode recherche
    search_fields = ('email', 'nom') 

    # Champs modifiables dans le formulaire de détail (ajout ou modification)
    fieldsets = (
        (None, {'fields': ('email', 'password')}), # Informations d'identification
        ('Informations personnelles', {'fields': ('nom', 'prenom', 'telephone', 'poste','localite')}),
        ('Permissions', {
            # Ajout des champs is_active, is_staff, is_superuser
            'fields': ('is_active', 'is_staff', 'is_superuser'), 
        }),
        
    )
    
    # Champs en lecture seule pour l'ajout, puis éditable en modification
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'nom', 'prenom', 'telephone', 'poste','localite', 'is_active', 'is_staff', 'is_superuser'),
        }),
    )
    
    # Ordering
    ordering = ('email',)

# Enregistrement du modèle avec la classe d'administration personnalisée
admin.site.register(Utilisateur, affiche)
admin.site.register(Plainte)
admin.site.register(RegistreArrive)