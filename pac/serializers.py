from rest_framework import serializers
from django.contrib.auth.models import Group
from utilisateur.models import Plainte, Localite, OPJ



class PlainteSerializer(serializers.ModelSerializer):
    pieces_jointes_url = serializers.SerializerMethodField()
    class Meta:
        model = Plainte
        fields = ['id', 'n_chrono_tkk','ny_mpitory','date_plainte','ilay_olona_kolikoly', 'toorna_birao', 'tranga_kolikoly', 'statut','piece_jointe','pieces_jointes_url'] 
    def get_pieces_jointes_url(self, obj):
        # Vérifie si le fichier existe et retourne son URL absolue
        if obj.piece_jointe:
            # Récupère le contexte 'request' passé dans la vue
            request = self.context.get('request') 
            if request is not None:
                # Utilise request pour construire l'URL complète (nécessaire pour l'APK)
                return request.build_absolute_uri(obj.piece_jointe.url)
            # Retourne l'URL relative si la requête n'est pas disponible (cas rare dans une API)
            return obj.piece_jointe.url 
        return None


class PlainteCreationSerializer(serializers.ModelSerializer):
    piece_jointe = serializers.FileField(required=False)
    date_plainte = serializers.DateField(required=False, input_formats=['%d/%m/%Y'])
    class Meta:
        model = Plainte 
        fields = ['ny_mpitory', 'tranga_kolikoly', 'ilay_olona_kolikoly', 'toorna_birao','piece_jointe','date_plainte']
    def validate_piece_jointe(self, value): 
        if value is None: 
            return value
            
        # 10 Mo = 10 * 1024 * 1024 octets
        max_file_size = 10 * 1024 * 1024 
        
        if value.size > max_file_size:
            raise serializers.ValidationError(
                f"La taille du fichier ne doit pas dépasser 10 Mo. Taille actuelle : {value.size / (1024 * 1024):.2f} Mo."
            )
        return value
    def validate_date_plainte(self, value):
        return value

class OPJSerializer(serializers.ModelSerializer):
    """Serializer pour l'affichage des données (Lecture)"""
    utilisateur_creation_nom = serializers.ReadOnlyField(source='utilisateur_creation.nom')

    class Meta:
        model = OPJ
        fields = '__all__'

class OPJCreationSerializer(serializers.ModelSerializer):
    """Serializer pour la création et la modification (Écriture)"""
    class Meta:
        model = OPJ
        # On exclut les champs gérés automatiquement ou par la vue
        exclude = ['utilisateur_creation', 'utilisateur_modification', 'n_chrono_opj']

    def validate_piece_jointe(self, value):
        # Optionnel : Ajouter une validation sur la taille du fichier (ex: 5Mo)
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Le fichier ne doit pas dépasser 5 Mo.")
        return value