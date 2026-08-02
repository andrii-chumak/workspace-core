from django.urls import path

from .views import BoardView, BoardColumnView, BoardColumnCreateView, BoardColumnsReorderView


app_name = "board"

urlpatterns = [
    path("<int:project_pk>/board/", BoardView.as_view(), name="board-detail"),
    path("board/<int:board_pk>/columns/", BoardColumnCreateView.as_view(), name="column-create"),
    path("board/<int:board_pk>/columns/reorder/", BoardColumnsReorderView.as_view(), name="column-reorder"),
    path("board/<int:board_pk>/columns/<int:column_pk>/", BoardColumnView.as_view(), name="column-detail-change-delete"),
]
