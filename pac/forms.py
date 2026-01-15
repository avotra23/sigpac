from cProfile import label
from django import forms
from django.contrib.auth.models import Group
from utilisateur.models import Plainte,RegistreArrive

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