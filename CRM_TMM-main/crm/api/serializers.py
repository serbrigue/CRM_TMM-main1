from rest_framework import serializers
import re


class EnrollSerializer(serializers.Serializer):
    nombre = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField()
    telefono = serializers.CharField(required=True, allow_blank=False, max_length=30)

    def validate_telefono(self, value):
        # Normalizar y validar que tenga entre 7 y 15 dígitos
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15:
            raise serializers.ValidationError('Número de teléfono inválido. Debe contener entre 7 y 15 dígitos.')
        return value
