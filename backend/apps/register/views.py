from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView


from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer

class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


User = get_user_model()

class CheckEmailView(APIView):
    def get(self, request):
        email = request.query_params.get("email")
        if not email:
            return Response(
                {"detail": "email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_taken = User.objects.filter(email__iexact=email).exists()
        return Response({"available": not is_taken})

