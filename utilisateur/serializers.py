

from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import Utilisateur, Plainte, Localite 


class UtilisateurSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )
    poste = serializers.StringRelatedField(read_only=True)
    localite = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom', 'prenom', 'poste', 'localite', 'groups', 'is_active']


class GroupSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'user_count']


class LocaliteSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Localite
        fields = ['id', 'nom', 'user_count'] 


class PlainteSerializer(serializers.ModelSerializer):
    pieces_jointes_url = serializers.SerializerMethodField()
    class Meta:
        model = Plainte
        fields = ['id', 'n_chrono_tkk', 'date_plainte','ilay_olona_kolikoly', 'toorna_birao', 'tranga_kolikoly', 'statut','piece_jointe','pieces_jointes_url'] 
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
    date_plainte = serializers.DateField(required=False)
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