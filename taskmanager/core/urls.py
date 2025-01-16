from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from . import views
from .views import RegistrationView, get_reporting_to_options

urlpatterns = [
    # Authentication URLs
    path('', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', RegistrationView.as_view(), name='register'),
    
    # Dashboard & Main Views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', views.lead_dashboard, name='lead_dashboard'),
    
    # Task Management
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('task/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('task/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    
    # Lead Management
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('lead-management/', views.lead_management, name='lead_management'),
    path('get-completed-leads/', views.get_completed_leads, name='get_completed_leads'),
    path('lead/<int:lead_id>/update-status/', views.update_lead_status, name='update_lead_status'),
    path('lead/<int:lead_id>/history/', views.get_lead_history, name='lead_history'),
    
    # Attendance Management
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('mark_checkout/', views.mark_attendance, name='mark_checkout'),
    
    # Reports & Notifications
    path('reports/', views.ReportView.as_view(), name='reports'),
    path('reports/export/', views.export_report, name='export_report'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', 
         views.mark_notification_read, name='mark_notification_read'),
    
    # API Endpoints
    path('get-reporting-to-options/', 
         get_reporting_to_options, name='get_reporting_to_options'),
    
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)