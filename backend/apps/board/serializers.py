from rest_framework import serializers

from .models import BoardColumn, Board



class BoardColumnSerializer(serializers.ModelSerializer):
    wip_limit = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    board_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = BoardColumn

        fields = (
            'id',
            'board_id',
            'name',
            'column_type',
            'position',
            'wip_limit',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id','position', 'board_id', 'created_at', 'updated_at')

        
class BoardSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(read_only=True)
    columns = BoardColumnSerializer(many=True, read_only=True)

    class Meta:
        model = Board

        fields = (
            "id",
            "project_id",
            "columns"
        )
        read_only_fields = ('id', 'project_id', 'columns')


class BoardColumnReorderSerializer(serializers.Serializer):
    column_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_column_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Column IDs must not contain duplicates."
            )

        return value