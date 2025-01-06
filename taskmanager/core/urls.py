from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.contrib.auth import views as auth_views
from .views import RegistrationView, get_reporting_to_options
urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', views.LogoutView.as_view(
        next_page='login'
    ), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('task/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('lead/<int:lead_id>/update-status/', views.update_lead_status, name='update_lead_status'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('mark_checkout/', views.mark_attendance, name='mark_checkout'),
    path('register/', RegistrationView.as_view(), name='register'),
    path('get-reporting-to-options/', get_reporting_to_options, name='get_reporting_to_options'),
    path('reports/', views.ReportView.as_view(), name='reports'),
    path('reports/export/', views.export_report, name='export_report'),
    path('lead/<int:lead_id>/history/', views.get_lead_history, name='lead_history'),
    path('tasks/',views.TaskListView.as_view(), name='task_list'),
    path('task/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('', views.lead_dashboard, name='lead_dashboard'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('lead-management/', views.lead_management, name='lead_management'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)