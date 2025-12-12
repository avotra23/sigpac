from cProfile import label
from django import forms
from django.contrib.auth.models import Group
from .models import Utilisateur,Plainte,RegistreArrive


class LoginForm(forms.ModelForm):
    email = forms.EmailField(label='Adresse e-mail')
    password=forms.CharField(label='Not de passe', widget=forms.PasswordInput)

class UtilisateurCreationForm(forms.ModelForm):
    password = forms.CharField(label='Mot de passe', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmer le mot de passe', widget=forms.PasswordInput)

    class Meta:
        model = Utilisateur
        fields = ('email','nom','prenom','telephone')
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")
        if password and password2 and password != password2 :
            self.add_error('password2',"Les motes de passe ne correspondemt pas")
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
    

class PublicInscription(UtilisateurCreationForm):
    pass

class OPJCreationForm(UtilisateurCreationForm):
    pass

class AdminCreationForm(UtilisateurCreationForm):
    group_choice = forms.ModelChoiceField(
        queryset= Group.objects.all().order_by('name'),
        label = "Groupe",
        required=True
    )
    class Meta:
        model = Utilisateur # ⬅️ Ajoutez explicitement le modèle
        fields = UtilisateurCreationForm.Meta.fields + ('poste','localite')
class AdminModificationForm(forms.ModelForm):
    # Les groupes sont souvent modifiés via une liste déroulante ou des cases à cocher
    groups = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label='Groupe/Rôle',
        empty_label="Aucun groupe"
    )
    
    # Ajoutez ces champs si vous voulez qu'ils soient modifiables
    is_active = forms.BooleanField(required=False, label='Est Actif')
    is_superuser = forms.BooleanField(required=False, label='Est Superutilisateur')

    class Meta:
        model = Utilisateur
        # Liste des champs que l'Admin peut modifier :
        fields = ['email', 'nom', 'prenom', 'telephone', 'poste', 'localite', 'groups', 'is_active', 'is_superuser']
        
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Adresse E-mail'}),
            'nom': forms.TextInput(attrs={'placeholder': 'Nom'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si le formulaire est chargé avec une instance (pour modification)
        if self.instance and self.instance.pk:
            current_group = self.instance.groups.first()
            
            if current_group:
                # Initialisez la valeur du champ 'groups' avec cet objet Group
                self.initial['groups'] = current_group
        if self.instance.groups.filter(name='Public').exists():
                # On rend les champs optionnels pour ne pas bloquer la validation
                self.fields['localite'].required = False
                self.fields['poste'].required = False
                
                self.fields['localite'].widget.attrs['class'] = 'field-public-hidden'
                self.fields['poste'].widget.attrs['class'] = 'field-public-hidden'

    # Cette méthode permet de sauvegarder le groupe correctement si le champ 'groups' est inclus
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Gestion de la relation ManyToMany pour les groupes
            if 'groups' in self.cleaned_data:
                group = self.cleaned_data['groups']
                user.groups.clear() # Supprime les anciens groupes
                if group:
                    user.groups.add(group) # Ajoute le nouveau groupe
        return user

MAX_UPLOAD_SIZE = 10485760 
MAX_UPLOAD_SIZE_DISPLAY = "10 Mo"
class PlainteForm(forms.ModelForm):
    def clean_piece_jointe(self):
        # Récupère le fichier téléversé
        uploaded_file = self.cleaned_data.get('piece_jointe')
        
        # Vérifie si un fichier a été téléversé
        if uploaded_file:
            # Vérifie la taille du fichier
            if uploaded_file.size > MAX_UPLOAD_SIZE:
                # Lance une erreur si la taille dépasse la limite
                raise forms.ValidationError(
                    f"La taille du fichier ne doit pas dépasser {MAX_UPLOAD_SIZE_DISPLAY}. "
                    f"Taille actuelle : {round(uploaded_file.size / (1024 * 1024), 2)} Mo."
                )
        
        # Retourne le fichier nettoyé (obligatoire dans la méthode clean)
        return uploaded_file
    class Meta:
        model = Plainte
        # Exclusion des champs n_chrono_tkk et date_plainte
        fields = ['ny_mpitory', 'tranga_kolikoly', 'ilay_olona_kolikoly', 'toorna_birao','piece_jointe']
        widgets = {
            'ny_mpitory': forms.Textarea(attrs={'class': 'form-control form-control-lg', 'rows': 6}),
            'tranga_kolikoly': forms.Textarea(attrs={'class': 'form-control form-control-md', 'rows': 4}),
            'ilay_olona_kolikoly': forms.Textarea(attrs={'class': 'form-control form-control-md', 'rows': 4, 'placeholder': 'Saisie obligatoire'}),
            'toorna_birao': forms.Textarea(attrs={'class': 'form-control form-control-md', 'rows': 4}),
        }
        labels = {
            'ny_mpitory': "Ny Mpitory (Le Plaignant)",
            'tranga_kolikoly': "Tranga Kolikoly (Le Fait/Acte de Corruption)",
            'ilay_olona_kolikoly': "Ilay Olona Manao kolikoly (L'auteur de la corruption)",
            'toorna_birao': "Toerana - Birao - Sampan-draharaha manao ilay kolikoly (Lieu - Bureau - Service de la corruption)",
            'piece_jointe': "Pièce(s) jointe(s) (Optionnel)",
        }


class RegistreArriveForm(forms.ModelForm):
    
    class Meta:
        model = RegistreArrive
        # n_enr_arrive est exclu car auto-généré
        # date_arrivee est exclus car auto-généré (mais affiché en lecture seule)
        fields = [
            'date_correspondance', 
            'nature', 
            'provenance', 
            'texte_correspondance', 
            'observation'
        ]
        widgets = {
            'date_correspondance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'nature': forms.Select(attrs={'class': 'form-select'}),
            'provenance': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'texte_correspondance': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'date_correspondance': "Date Correspondance",
            'nature': "Nature",
            'provenance': "Provenance",
            'texte_correspondance': "Texte de la correspondance",
            'observation': "Observation",
        }