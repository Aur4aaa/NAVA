from django.urls import include, path
urlpatterns = [path('', include('workspace.urls'))]
handler403 = 'workspace.views.permission_denied'
handler404 = 'workspace.views.not_found'
handler500 = 'workspace.views.server_error'
