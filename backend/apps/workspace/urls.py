from django.urls import path
from .views import (
    WorkspacesView,
    WorkspaceView,
    WorkspaceMembersView,
    WorkspaceMemberView,
    LeaveWorkspaceView,
    TransferOwnershipView,
    WorkspaceArchiveView,
    WorkspaceRestoreView
)

urlpatterns = [
    path("", WorkspacesView.as_view(), name="workspace-list-create"),
    path("<int:workspace_pk>/", WorkspaceView.as_view(), name="workspace-get-update-delete"),
    path("<int:workspace_pk>/archive/", WorkspaceArchiveView.as_view(), name="workspace_archive"),
    path("<int:workspace_pk>/restore/", WorkspaceRestoreView.as_view(), name="workspace-restore",),
    path("<int:workspace_pk>/leave/", LeaveWorkspaceView.as_view(), name="workspace_leave"),
    path("<int:workspace_pk>/transfer-ownership/", TransferOwnershipView.as_view(), name="workspace-transfer-ownership"),
    path("<int:workspace_pk>/members/", WorkspaceMembersView.as_view(), name="workspace_members-list-add"),
    path("<int:workspace_pk>/members/<int:member_pk>/", WorkspaceMemberView.as_view(), name="workspace_member-get-change-delete"),
]
