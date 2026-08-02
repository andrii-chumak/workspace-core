from .models import Board, BoardColumn

DEFAULT_COLUMNS = (
    ("To Do", BoardColumn.ColumnType.TODO),
    ("In Progress", BoardColumn.ColumnType.IN_PROGRESS),
    ("In Review", BoardColumn.ColumnType.IN_REVIEW),
    ("Done", BoardColumn.ColumnType.DONE),
)

def create_default_board(project):

    board = Board.objects.create(
        project=project,
    )

    for position, (name, column_type) in enumerate(
        DEFAULT_COLUMNS,
        start = 1
    ):
        BoardColumn.objects.create(
            board=board,
            position=position,
            name=name,
            column_type=column_type,
        )

    return board


