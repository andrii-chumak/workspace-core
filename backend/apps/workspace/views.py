from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .serializers import WorkspaceSerializer

class WorkspaceView(APIView):
    def post (self, request):
        pass