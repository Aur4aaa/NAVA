from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('health/', views.health, name='health'),
    path('accounts/login/', views.WorkspaceLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('roadmap/', views.roadmap, name='roadmap'),
    path('traceability/', views.traceability, name='traceability'),
    path('search/', views.search, name='search'),
    path('approvals/', views.approvals, name='approvals'),
    path('settings/', views.settings_page, name='settings'),
    path('records/<slug:kind>/', views.record_list, name='record-list'),
    path('records/<slug:kind>/new/', views.record_create, name='record-create'),
    path('records/<slug:kind>/export/<str:format>/', views.export_records, name='record-export'),
    path('records/<slug:kind>/<int:pk>/', views.record_detail, name='record-detail'),
    path('records/<slug:kind>/<int:pk>/edit/', views.record_edit, name='record-edit'),
    path('records/<slug:kind>/<int:pk>/action/<slug:action>/', views.record_action, name='record-action'),
    path('records/<slug:kind>/<int:pk>/share/', views.record_share, name='record-share'),
    path('evidence/<int:pk>/download/', views.evidence_download, name='evidence-download'),
    path('packs/<int:pk>/download/', views.pack_download, name='pack-download'),
]
