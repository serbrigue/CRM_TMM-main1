from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404

from ..utils.enrollment import enroll_cliente_en_taller
from ..models import Taller
from .serializers import EnrollSerializer


class EnrollTallerAPIView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, taller_id):
        serializer = EnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nombre = serializer.validated_data.get('nombre', '')
        email = serializer.validated_data['email']
        telefono = serializer.validated_data.get('telefono')

        usuario = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None

        # Validamos existencia del taller
        get_object_or_404(Taller, pk=taller_id)

        inscripcion, created, msg = enroll_cliente_en_taller(taller_id, nombre, email, telefono=telefono, usuario=usuario)

        if created:
            return Response({'message': msg, 'inscripcion_id': inscripcion.id}, status=status.HTTP_201_CREATED)
        else:
            if msg == 'No hay cupos disponibles':
                return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
            if msg.startswith('Cliente ya inscrito'):
                return Response({'detail': msg}, status=status.HTTP_409_CONFLICT)
            return Response({'detail': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
