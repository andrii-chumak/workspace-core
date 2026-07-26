from rest_framework import serializers

from .models import Workspace, WorkspaceMember

class WorkspaceSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Workspace
        fields = '__all__'

class WorkspaceMemberSerializer(serializers.ModelSerializer):
    joined_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = '__all__'


