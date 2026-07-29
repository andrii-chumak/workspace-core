from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import KanbanViewSet, ProjectViewSet, ScrumViewSet, SprintEventViewSet, SprintViewSet

router = DefaultRouter()
router.register("scrum", ScrumViewSet, basename="scrum")
router.register("kanban", KanbanViewSet, basename="kanban")
router.register("sprints", SprintViewSet, basename="sprint")
router.register("sprint-events", SprintEventViewSet, basename="sprint-event")
router.register("", ProjectViewSet, basename="project")

urlpatterns = [
    path("", include(router.urls)),
]
